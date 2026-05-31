import sys

from dotenv import load_dotenv

from util.healthcheck import healthcheck
from util.logging import logger


def main():
    logger.info("Hello from python-starter!")


if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
        healthcheck()
    else:
        main()
