"""Event tracker backend that discards events."""

from __future__ import absolute_import

from track.backends import BaseBackend


class NullBackend(BaseBackend):
    """Event tracker backend that does nothing.

        Events are just discarded.
    """

    def send(self, event):
        pass
