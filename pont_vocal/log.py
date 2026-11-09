import logging


def setup_log(stream):
    logging.basicConfig(
        stream=stream,
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
