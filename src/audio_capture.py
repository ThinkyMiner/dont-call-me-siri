from collections import deque
from typing import Callable, Optional
import sounddevice as sd


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
        pre_buffer_duration_ms: int = 400,
        device_id: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.pre_buffer_chunks = int(pre_buffer_duration_ms / chunk_duration_ms)
        self.pre_buffer: deque[bytes] = deque(maxlen=self.pre_buffer_chunks)
        self.device_id = device_id
        self._stream = None
        self._callback: Optional[Callable[[bytes], None]] = None

    def _handle_audio(self, indata, frames, time_info, status):
        data = bytes(indata)
        self.pre_buffer.append(data)
        if self._callback:
            self._callback(data)

    def start(self, callback: Callable[[bytes], None]) -> None:
        self._callback = callback
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk_size,
                device=self.device_id,
                callback=self._handle_audio,
            )
            self._stream.start()
        except sd.PortAudioError as exc:
            input_devices = self.list_devices()
            if not input_devices:
                raise RuntimeError(
                    "No input audio devices were found. Connect/enable a microphone, "
                    "then run `python -m src.main devices` to verify."
                ) from exc
            raise RuntimeError(
                "Could not open the audio input device. Set `audio.device_id` in config.json "
                "to one of the indices from `python -m src.main devices`."
            ) from exc

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_pre_buffer(self) -> bytes:
        return b"".join(self.pre_buffer)

    def clear_pre_buffer(self) -> None:
        self.pre_buffer.clear()

    @staticmethod
    def list_devices() -> list[dict]:
        try:
            devices = sd.query_devices()
        except sd.PortAudioError:
            return []
        return [
            {"index": i, "name": d["name"]}
            for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
