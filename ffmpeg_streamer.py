from typing import List
import platform

def build_ffmpeg_stream_cmd(
    input_source: str,
    output_ip: str,
    output_port: int,
    is_file: bool = False,
    gpu_codec: str = None,
    loop: bool = False
) -> List[str]:
    """
    Формирует ffmpeg-команду для захвата с устройства или файла, с GPU/CPU-кодированием, и стриминга по UDP.

    Parameters:
        input_source (str): путь к файлу (если is_file=True) или имя видеоустройства
        output_ip (str): адрес получателя потока
        output_port (int): порт получателя
        is_file (bool): True — если источник это видеофайл
        gpu_codec (str or None): например, "h264_nvenc", "h264_qsv", "h264_vaapi"; None — fallback на libx264
        loop (bool): зацикливать видеофайл

    Returns:
        List[str]: готовая ffmpeg-команда
    """

    system = platform.system()
    input_args = []

    if is_file:
        input_args = ["-re"]
        if loop:
            input_args += ["-stream_loop", "-1"]
        input_args += ["-i", input_source]

    else:
        if system == "Windows":
            input_args = ["-f", "dshow", "-i", input_source]
        elif system == "Darwin":
            input_args = ["-f", "avfoundation", "-i", input_source]
            if gpu_codec == "h264_nvenc":
                gpu_codec = "h264_videotoolbox"
        elif system == "Linux":
            input_args = ["-f", "v4l2", "-i", input_source]
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    # Кодек: GPU или CPU fallback
    codec = gpu_codec if gpu_codec else "libx264"

    ffmpeg_cmd = [
        "ffmpeg",
        *input_args,
        "-vf", "format=yuv420p",               # конвертация, особенно для захвата
        "-c:v", codec,
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "50",
        "-keyint_min", "50",
        "-sc_threshold", "0",
        "-x264-params", "repeat-headers=1",    # важен для mpegts потока
        "-f", "mpegts",
        f"udp://{output_ip}:{output_port}"
    ]

    return ffmpeg_cmd
