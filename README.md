# youtube-notify

`youtube-notify` is a small Python library for fetching recent content from a YouTube channel. It prefers the channel RSS feed first and falls back to the YouTube Data API when RSS does not return content. The library returns typed `Content` models with channel metadata, timestamps, thumbnails, and descriptions.

## Features

- RSS-first content retrieval with YouTube API fallback
- Optional YouTube API key and OAuth helpers
- Pydantic models for downstream validation and serialization
- Async-friendly public APIs
- Mocked integration tests for deterministic CI runs

## Installation

This repository uses a `src/` layout and installs as the `youtube_notify` package.

```bash
git clone https://github.com/jnstockley/youtube-notify.git
cd youtube-notify
uv sync
```

If you are using another virtual environment tool, install the project from `pyproject.toml` so the package is available as `youtube_notify`.

## Setup

1. Clone the repository.
2. Create and activate a Python 3.14 environment.
3. Install dependencies with `uv sync` or your preferred environment manager.
4. Set `PYTHONPATH=src` when running the library directly from the repository.
5. If you want to use the YouTube API fallback, provide an API key or OAuth credentials in your own application code.

## Usage

The main entry point is `youtube_notify.get_content(channel_id, youtube=None)`.
It tries RSS first and only uses the YouTube API client if RSS returns no content.

### Basic usage

```python
import asyncio

from youtube_notify import get_content


async def main() -> None:
    content = await get_content("UCxxxxxxxxxxxxxxxxxxxxxx")
    for item in content:
        print(item.title)


asyncio.run(main())
```

### Using a YouTube API key

If you already have a YouTube Data API key, build a client with `youtube_notify.youtube.auth.api_key.authenticate()` and pass it to `youtube_notify.get_content()`.

```python
import asyncio

from youtube_notify import get_content
from youtube_notify.youtube.auth.api_key import authenticate


async def main() -> None:
    youtube = authenticate("YOUR_YOUTUBE_API_KEY")
    content = await get_content("UCxxxxxxxxxxxxxxxxxxxxxx", youtube)
    for item in content:
        print(item.title)


asyncio.run(main())
```

### Using OAuth credentials

If you need OAuth-based access, the OAuth helper can build credentials and refresh them before creating the client.

```python
from youtube_notify.youtube.auth.oauth import authenticate, device_code_flow


creds = device_code_flow("YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET")
youtube = authenticate(creds)
```

## Required Environment Variables

The library itself does not require API credentials from environment variables. The only runtime environment settings used by the code are for logging:

- `LOG_LEVEL`: optional, defaults to `INFO`
- `LOG_DIR`: optional, defaults to `../logs`

The repository also includes `sample.env` with example values for a wrapper application:

- `YOUTUBE_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

Those are not read automatically by the library; they are intended for your own application or deployment scripts.

If your application uses the YouTube API path through `youtube_notify.youtube.get_content()` or
passes a client into `youtube_notify.get_content()`, you must provide one of the
following sets of credentials in your application layer:

- `YOUTUBE_API_KEY`
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`

## Development

Common local commands:

```bash
uv run pytest
uv run pytest -m integration
uv run ruff check
uv run ruff format --check
```

The integration test suite is mocked and does not make live network calls.

## Project Structure

- `src/youtube_notify/content_fetcher.py`: top-level RSS-first content fetcher
- `src/youtube_notify/rss/rss.py`: RSS feed fetching and parsing
- `src/youtube_notify/youtube/youtube.py`: YouTube API fetching and parsing
- `src/youtube_notify/youtube/auth/`: API key and OAuth helpers
- `src/youtube_notify/models.py`: Pydantic models used across the library

## Operational Notes

- The library writes logs to `LOG_DIR/app.log`.
- If you run the code in a container or read-only environment, set `LOG_DIR` to a writable path.
- The public APIs are asynchronous, so call them from `asyncio` code or wrap them with `asyncio.run()`.

## Contributing

Contributions are expected to keep the repository green.

Before opening a pull request:

- All tests must pass.
- Code coverage for updated code should be at least 90%.
- The existing linting steps must pass.
- Any public behavior change should include matching tests.

Recommended validation commands:

```bash
uv run pytest
uv run pytest --cov src --cov-branch --cov-report=term-missing
uv run ruff check
uv run ruff format --check
```

## License

This project is licensed under the GNU General Public License v3.0. See the `LICENSE` file for details.
