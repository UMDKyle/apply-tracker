from pathlib import Path
import os

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"

import pygame


def play_sound_windows(audio_path: str) -> None:
    """
    Play audio without opening a visible media player window.
    
    Uses pygame.mixer for background audio playback.
    Supports MP3, WAV, OGG formats.
    """
    p = Path(audio_path)
    
    # If relative path, resolve it relative to cwd
    if not p.is_absolute():
        p = Path.cwd() / p
    
    if not p.exists():
        raise FileNotFoundError(f"Audio file not found: {p.resolve()}")

    # Initialize pygame mixer if not already initialized
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    
    # Play sound and wait for it to finish
    sound = pygame.mixer.Sound(str(p.resolve()))
    channel = sound.play()
    
    # Wait until the sound finishes playing
    while channel.get_busy():
        pygame.time.wait(100)  # Wait 100ms between checks
