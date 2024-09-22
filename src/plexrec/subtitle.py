import re
from abc import ABC, abstractmethod
from io import BytesIO
from zipfile import ZipFile

import requests

# TODO: Add cleaning functions for all common subtitle formats and a function to determine which format it is.


def clean_srt(subtitle: str):
    """
    Remove everything from a .srt file except the subtitles themselves, which is all that we need.
    """

    # Remove this stupid \uFEFF thing.
    subtitle = re.sub(r"\ufeff", "", subtitle, re.I)

    # Remove carriage returns (F*CKING WINDOWS BREAKING MY REGEX).
    subtitle = re.sub(r"\r", "", subtitle)

    # Remove the subtitle number indicators and the timestamps.
    subtitle = re.sub(
        r"^\d+$\n^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$\n",
        "",
        subtitle,
        0,
        flags=re.M,
    )

    # Remove formatting and fonts.
    subtitle = re.sub(r"([<{])(b|i|u|font).*?([>}])(.*?)\1/\2\3", r"\4", subtitle)

    # Remove {\a#} things.
    subtitle = re.sub(r"{\\a\d+}", "", subtitle)

    # Shrink consecutive newlines to single newlines.
    subtitle = re.sub(r"\n+", r"\n", subtitle)
    # print(subtitle)
    return subtitle


class SubtitleNotFoundException(Exception):
    pass


class SubtitleProvider(ABC):
    @abstractmethod
    def get_srt(self, imdb: str, language: str = "English") -> str:
        pass


class Subscene(SubtitleProvider):
    def __init__(self) -> None:
        super().__init__()
        self.page_id_regex = re.compile(r"/subscene/(\d+)")
        # # I will be completely honest, I have no idea how this regex works. I just adapted it from:
        # # https://stackoverflow.com/questions/27938851/regex-select-closest-match
        # self.subtitle_id_regex = re.compile(
        #     r"(?s)/subtitle/(\d+)(?:(?!/subtitle/(\d+)).)*?English"
        # )
        self.subtitles_regex = re.compile(
            r"<td class=\"a1\">.*?/subtitle/(?P<id>\d+).*?neutral-icon\">\s+(?P<language>.*?)\s+</span>.*?class=\"new\">\s+(?P<name>.*?)\s*?</span>.*?class=\"a3\">\s+(?P<files>\d+).*?href=\"/u/\d+\">\s+(?P<owner>.*?)\s+</a>",
            flags=re.MULTILINE | re.DOTALL,
        )

    def get_srt(self, imdb: str, language: str = "English") -> str:
        search_results_page = requests.get(
            f"https://subscene.best/search?query={imdb}",
            allow_redirects=True,
            timeout=5,
        )
        page_id = self.page_id_regex.search(search_results_page.text).group(1)

        subtitles_page = requests.get(
            f"https://subscene.best/subscene/{page_id}", allow_redirects=True, timeout=5
        )
        subtitle_list = re.findall(self.subtitles_regex, subtitles_page.text)
        # Filter to only subtitles with the requested language and 1 file.
        subtitle_list = [
            sub for sub in subtitle_list if sub[1] == language and sub[3] == "1"
        ]

        subtitle_id = None
        for subtitle in subtitle_list:
            url = f"https://subscene.best/download/{subtitle[0]}"
            response = requests.get(
                url,
                headers={
                    "Range": "bytes=0-172"
                },  # Retrieve only first 172 bytes to check if it's a zip file.
                # It should be the first 2 bytes, but the file starts at 172 bytes in for some reason.
            )

            # Fail if the server didn't return partial content.
            if response.status_code != 206:
                continue

            # Fail if the file doesn't start with the .zip header (which decodes to PK).
            # In this case, the "file" starts at 170 bytes in because of some weird error on the Subscene server.
            if not response.content.endswith(b"PK"):
                continue

            subtitle_id = subtitle[0]
            break

        if subtitle_id is None:
            raise SubtitleNotFoundException()

        url = f"https://subscene.best/download/{subtitle_id}"
        subtitle_response = requests.get(
            url,
            allow_redirects=True,
        )
        # TODO: Add support for recognizing and decompressing non-zip files.
        with ZipFile(BytesIO(subtitle_response.content)) as zipped:
            return zipped.read(zipped.filelist[0].filename).decode()


class Podnapisi(SubtitleProvider):
    def __init__(self) -> None:
        super().__init__()
        self.page_id_regex = re.compile(r"/subscene/(\d+)")
        # I will be completely honest, I have no idea how this regex works. I just adapted it from:
        # https://stackoverflow.com/questions/27938851/regex-select-closest-match
        self.subtitle_id_regex = re.compile(
            r"(?s)/subtitle/(\d+)(?:(?!/subtitle/(\d+)).)*?English"
        )

    def get_subtitle(self, imdb: str, language: str = "English") -> str:
        search_results_page = requests.get(
            f"https://www.moviesubtitles.org/search.php?q=",
            allow_redirects=True,
            timeout=5,
        )
        print("First")
        page_id = self.page_id_regex.search(search_results_page.text).group(1)

        subtitles_page = requests.get(
            f"https://subscene.best/subscene/{page_id}", allow_redirects=True, timeout=5
        )
        print("Second")
        print(re.sub(r"([\t\n])+", r"\g<1>", subtitles_page.text))
        subtitle_id = self.subtitle_id_regex.search(subtitles_page.text).group(1)

        url = f"https://subscene.best/download/{subtitle_id}"
        print(url)
        subtitle_response = requests.get(
            url,
            allow_redirects=True,
            # stream=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-US,en;q=0.5",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
            },
            cookies={"PHPSESSID": "p6fto9apqj6dkggmoqji8ohn70"},
        )
        print("The unzip process begins...")
        print(subtitle_response.text[:4])
        with open("subtitle.zip", "wb") as f:
            f.write(subtitle_response.content)
        return "subtitle_zip"


if __name__ == "__main__":
    subtitle = Subscene().get_srt(input("IMDB ID > "))
    clean = clean_srt(subtitle)
    print(clean)
    print(len(clean))
    print()