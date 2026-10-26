import logging


class ASCIIFormatter(logging.Formatter):
    """Keep application log output safe for ASCII-only terminals."""

    def format(self, record):
        message = super().format(record)
        return message.encode('ascii', 'backslashreplace').decode('ascii')
