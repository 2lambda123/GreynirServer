#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    Friendly command line interface for Icelandic speech synthesis.
    Returns 0 on success, 1 on error.

"""

from typing import Optional

import os
import sys
import logging
from urllib.request import urlopen
import wave

import requests

from speech import (
    text_to_audio_url,
    DEFAULT_VOICE,
    SUPPORTED_VOICES,
    DEFAULT_TEXT_FORMAT,
    DEFAULT_AUDIO_FORMAT,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_TEXT_FORMATS,
)
from speech.voices import suffix_for_audiofmt, is_data_uri
from utility import icelandic_asciify


def _bytes4data_uri(data_uri: str) -> bytes:
    """Returns data contained in data URI (RFC2397) as bytes."""
    with urlopen(data_uri) as response:
        return response.read()


def _fetch_audio_bytes(url: str) -> Optional[bytes]:
    """Returns bytes of audio file at URL."""
    if is_data_uri(url):
        return _bytes4data_uri(url)

    try:
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception(
                f"Received HTTP status code {r.status_code} when fetching {url}"
            )
        return r.content
    except Exception as e:
        logging.error(f"Error fetching audio bytes: {e}")


def _play_audio_file(path: str) -> None:
    """Play audio file at path via command line player. This only
    works on systems with either afplay (macOS) or mpg123 (Linux)."""

    AFPLAY = "/usr/bin/afplay"  # afplay is only present on macOS systems
    MPG123 = "mpg123"

    if os.path.exists(AFPLAY):
        print(f"Playing file '{path}'")
        os.system(f"{AFPLAY} '{path}'")
    else:
        print(f"Playing file '{path}'")
        os.system(f"{MPG123} --quiet '{path}'")


DEFAULT_TEXT = "Góðan daginn og til hamingju með lífið."


def main() -> None:
    """Main program function."""
    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument(
        "-v",
        "--voice",
        help="specify which voice to use",
        default=DEFAULT_VOICE,
        choices=list(SUPPORTED_VOICES),
    )
    parser.add_argument(
        "-f",
        "--audioformat",
        help="select audio format",
        default=DEFAULT_AUDIO_FORMAT,
        choices=list(SUPPORTED_AUDIO_FORMATS),
    )
    parser.add_argument(
        "-s",
        "--speed",
        help="set speech speed",
        default=1.0,
        type=float,
    )
    parser.add_argument(
        "-t",
        "--textformat",
        help="set text format",
        default=DEFAULT_TEXT_FORMAT,
        choices=list(SUPPORTED_TEXT_FORMATS),
    )
    parser.add_argument(
        "-o",
        "--override",
        help="override default audio output filename",
        default="",  # Empty string means use default filename
    )
    parser.add_argument(
        "-w", "--wav", help="generate WAV file from PCM", action="store_true"
    )
    parser.add_argument(
        "-u", "--url", help="just dump audio URL to stdout", action="store_true"
    )
    parser.add_argument(
        "-n", "--noplay", help="do not play resulting audio file", action="store_true"
    )
    parser.add_argument(
        "text",
        help="text to synthesize",
        nargs="?",
        default=DEFAULT_TEXT,
    )

    args = parser.parse_args()

    def die(msg: str, exit_code: int = 1) -> None:
        print(msg, file=sys.stderr)
        sys.exit(exit_code)

    if len(args.text.strip()) == 0:
        die("No text provided.")

    if args.wav and args.audioformat != "pcm":
        die("WAV output flag only supported for PCM format.")

    # Synthesize the text according to CLI options
    url = text_to_audio_url(
        args.text,
        text_format=args.textformat,
        audio_format=args.audioformat,
        voice_id=args.voice,
        speed=args.speed,
    )
    if not url:
        die("Error generating speech synthesis URL.")

    if args.url:
        print(url)
        sys.exit(0)

    # Download
    urldesc = "data URI" if is_data_uri(url) else url
    print(f"Fetching {urldesc}")
    data: Optional[bytes] = _fetch_audio_bytes(url)
    if not data:
        die("Unable to fetch audio data.")

    assert data is not None  # Silence typing complaints

    if args.override:
        # Override default filename
        fn = args.override
    else:
        # Generate default file name based on text and audio format
        fn = "_".join([t.lower() for t in args.text.rstrip(".").split()])
        fn = fn.replace(",", "").rstrip(".").replace("?", "").replace("!", "")
        fn = icelandic_asciify(fn)[:60].rstrip("_")  # Rm non-ASCII chars + limit length
        suffix = "wav" if args.wav else suffix_for_audiofmt(args.audioformat)
        fn = f"{fn}.{suffix}"

    # Write audio data to file
    print(f'Writing to file "{fn}".')
    if args.wav:
        # The PCM audio needs a WAV header
        wav = wave.open(fn, "wb")
        # We assume that the data is in this format, i.e. mono 16-bit signed 16 kHz PCM
        # This will stop working if the speech synthesis modules start delivering PCM
        # in a different format but that's OK. This exists for purely in-house purposes.
        wav.setnchannels(1)  # mono
        wav.setsampwidth(2)  # 16 bit
        wav.setframerate(16000)  # 16 kHz
        wav.writeframes(data)
        wav.close()
    else:
        with open(fn, "wb") as f:
            f.write(data)

    # Play audio file using command line tool (if available)
    if not args.noplay:
        _play_audio_file(fn)


if __name__ == "__main__":
    """Perform speech synthesis of Icelandic text via the command line."""
    main()
