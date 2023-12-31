import datetime
import logging
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ffmpeg import FFmpegError, Progress
from ffmpeg.asyncio import FFmpeg
from ffmpeg.types import asyncio
from ffmpeg.utils import re

PATH = Path(os.getenv("OUTPUT_PATH", "downloads"))
PATH.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


class Downloader:
    def __init__(
        self, url: str, progress_interval: int, output_file: str = "output.mkv"
    ):
        self._url = url
        self._progress_interval = progress_interval
        self._status = DownloadStatus(
            duration=datetime.timedelta(),
            time=datetime.timedelta(),
            play_speed=0,
            current_size=0,
            status="PROGRESS",
        )
        self._output_file = PATH / output_file
        self._task: asyncio.Task | None = None
        self._ffmpeg_process: FFmpeg | None = None
        self._stderr: str = ""

    def on_start(self, arguments: list[str]):
        logger.info("Download Started with arguments", arguments)

    def on_stderr(self, line: str):
        logger.info(f"stderr:{self._output_file.name}- " + line)
        self._stderr += line + "\n"
        if not self._status.duration:
            ob = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})", line)
            if ob:
                self._status.duration = datetime.timedelta(
                    hours=int(ob.group(1)),
                    minutes=int(ob.group(2)),
                    seconds=int(ob.group(3)),
                )

    def on_progress(self, progress: Progress):
        # print("Progress", progress)
        self._status.time = progress.time
        self._status.play_speed = progress.speed
        self._status.current_size = progress.size
        self._status.status = "PROGRESS"

    def on_completed(self):
        logger.info(f"Completed: {self._output_file.name}")
        self._status.status = "COMPLETED"

    def on_terminated(self):
        logger.info(f"Terminated: {self._output_file.name}")
        self._status.status = "TERMINATED"

    def get_stderr(self):
        return self._stderr

    async def cancel_download(self):
        if self._ffmpeg_process:
            self._ffmpeg_process.terminate()
            try:
                self._output_file.unlink()
            except FileNotFoundError:
                pass
            return True
        return False

    async def download(self):
        ffmpeg = (
            FFmpeg()
            .option("i", self._url)
            .option("bsf:a", "aac_adtstoasc")
            .output(
                self._output_file,
                c="copy",
            )
        )
        ffmpeg.on("start", self.on_start)
        ffmpeg.on("stderr", self.on_stderr)
        ffmpeg.on("progress", self.on_progress)
        ffmpeg.on("completed", self.on_completed)
        ffmpeg.on("terminated", self.on_terminated)

        self._ffmpeg_process = ffmpeg
        self._task = asyncio.create_task(ffmpeg.execute())

        def on_task_end(task: asyncio.Task):
            try:
                task.result()
            except FFmpegError as e:
                logger.error(
                    f"Error: {self._output_file.name}",
                    exc_info=e,
                )
                self._status.error = e

        self._task.add_done_callback(on_task_end)

        is_done = False

        while True:
            if is_done:
                break

            if self._task.cancelled():
                is_done = True
                yield self._status
                continue

            if (
                self._status.status == "COMPLETED"
                or self._status.status == "TERMINATED"
            ):
                is_done = True
                yield self._status
                continue

            await asyncio.sleep(self._progress_interval)
            yield self._status


@dataclass
class DownloadStatus:
    duration: datetime.timedelta
    time: datetime.timedelta
    play_speed: float
    current_size: int
    status: Literal["COMPLETED"] | Literal["TERMINATED"] | Literal["PROGRESS"]
    error: FFmpegError | None = None

    def get_error_stack(self):
        if self.error:
            stack = traceback.format_exception(
                type(self.error), self.error, self.error.__traceback__
            )
            return "\n".join(stack)
        raise ValueError("No error found")

    def __str__(self):
        return (
            f"Duration: {self.duration}\n"
            f"Status: {self.status}\n"
            f"Time: {self.time}\n"
            f"Speed: {self.play_speed}x\n"
            f"Size: {round(self.current_size / 1_000_000, 2)}MB"
        )
