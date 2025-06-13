import subprocess
import platform
import shutil
import os
from typing import List
import copy
from tech_utils.logger import init_logger

logger = init_logger(name="FFMPEG_Accel", component="tech_utils")

def cmd_ok(cmd):
    try:
        subprocess.check_output(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.debug(f"Command failed: {' '.join(cmd)} | {e}")
        return False

def ffmpeg_has_hwaccel(accel_name):
    """Check if FFmpeg reports support for a specific hardware accelerator."""
    try:
        output = subprocess.check_output(['ffmpeg', '-hwaccels'], stderr=subprocess.DEVNULL)
        result = accel_name.encode() in output
        logger.debug(f"FFmpeg reports hwaccel '{accel_name}': {result}")
        return result
    except Exception as e:
        logger.warning(f"Failed to query ffmpeg -hwaccels: {e}")
        return False

def detect_reliable_hwaccel():
    """Detect the most reliable hardware acceleration backend for FFmpeg, based on the current OS and environment."""
    system = platform.system().lower()
    logger.info(f"Detected platform: {system}")

    if not shutil.which('ffmpeg'):
        logger.error("FFmpeg not found in PATH.")
        return None

    # macOS: use VideoToolbox if available
    if system == 'darwin':
        if ffmpeg_has_hwaccel('videotoolbox'):
            logger.info("Selected hwaccel: videotoolbox (macOS)")
            return 'videotoolbox'
        else:
            logger.info("videotoolbox not available in FFmpeg.")

    # Windows: try CUDA → QSV → DXVA2
    elif system == 'windows':
        if ffmpeg_has_hwaccel('cuda') and shutil.which('nvidia-smi'):
            try:
                subprocess.check_output(['nvidia-smi'], stderr=subprocess.DEVNULL)
                logger.info("Selected hwaccel: cuda (Windows + NVIDIA GPU)")
                return 'cuda'
            except Exception as e:
                logger.warning(f"nvidia-smi failed despite cuda being listed: {e}")

        if ffmpeg_has_hwaccel('qsv'):
            logger.info("Selected hwaccel: qsv (Windows + Intel iGPU)")
            return 'qsv'

        if ffmpeg_has_hwaccel('dxva2'):
            logger.info("Selected hwaccel: dxva2 (Windows fallback)")
            return 'dxva2'

    # Linux: try CUDA → QSV → VAAPI
    elif system == 'linux':
        if ffmpeg_has_hwaccel('cuda') and os.path.exists('/dev/nvidiactl'):
            logger.info("Selected hwaccel: cuda (Linux + NVIDIA GPU)")
            return 'cuda'

        if ffmpeg_has_hwaccel('qsv') and os.path.exists('/dev/dri/renderD128'):
            logger.info("Selected hwaccel: qsv (Linux + Intel iGPU)")
            return 'qsv'

        if ffmpeg_has_hwaccel('vaapi') and os.path.exists('/dev/dri/renderD128') and cmd_ok(['vainfo']):
            logger.info("Selected hwaccel: vaapi (Linux + Intel/AMD GPU)")
            return 'vaapi'

    logger.info("No reliable hardware acceleration backend detected.")
    return None


def run_ffmpeg_decoder_with_hwaccel(
    cmd: List[str],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL
) -> subprocess.Popen:
    """
    Run FFmpeg with hardware acceleration if supported (excluding videotoolbox),
    and add hwdownload + format=yuv420p if needed to read raw frames.
    Falls back to original command on failure.
    """

    hwaccel = detect_reliable_hwaccel()

    # Skip videotoolbox entirely — doesn't support rawvideo + stdout
    if hwaccel == "videotoolbox":
        logger.info("Skipping 'videotoolbox' for rawvideo output (not supported).")
        hwaccel = None

    if hwaccel:
        logger.info(f"Trying to run ffmpeg with hwaccel: {hwaccel}")
        cmd_hw = copy.deepcopy(cmd)

        try:
            # Insert -hwaccel <type>
            insert_index = 1 if cmd[0] == "ffmpeg" else 0
            cmd_hw.insert(insert_index + 1, hwaccel)
            cmd_hw.insert(insert_index + 1, "-hwaccel")

            # Add -vf hwdownload,format=yuv420p
            if "-vf" not in cmd_hw:
                try:
                    f_index = cmd_hw.index("-f")
                    cmd_hw.insert(f_index, "hwdownload,format=yuv420p")
                    cmd_hw.insert(f_index, "-vf")
                except ValueError:
                    cmd_hw += ["-vf", "hwdownload,format=yuv420p"]

            logger.debug(f"Running FFmpeg with hwaccel: {' '.join(cmd_hw)}")

            proc = subprocess.Popen(
                cmd_hw,
                stdout=stdout,
                stderr=stderr,
                stdin=stdin
            )

            # Briefly wait to catch early failure
            import time
            time.sleep(0.5)
            if proc.poll() is not None:
                logger.warning("FFmpeg with hwaccel failed to start, falling back to CPU.")
                proc.kill()
                raise RuntimeError("FFmpeg with hwaccel failed")
            return proc

        except Exception as e:
            logger.error(f"Failed to launch ffmpeg with hwaccel '{hwaccel}': {e}")

    # Fallback to CPU
    logger.info("Running FFmpeg without hardware acceleration.")
    return subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin
    )