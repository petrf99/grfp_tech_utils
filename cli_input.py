import sys
import select

def timed_input(prompt="", timeout=1.0):
    print(prompt, end="", flush=True)
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        return sys.stdin.readline().strip()
    return None

def input_with_back(prompt=""):
    user_input = input(f"{prompt}")
    if user_input.lower() == "back":
        return None
    return user_input