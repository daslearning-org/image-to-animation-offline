import os

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout

from kivymd import uix_path
from kivymd.theming import ThemableBehavior

Builder.load_string('''
<MyMDDivider>
    canvas:
        Color:
            rgba: (self.color)
        Rectangle:
            size: self.size
            pos: self.pos
''')


class MyMDDivider(ThemableBehavior, BoxLayout):
    """
    A divider line.

    .. versionadded:: 2.0.0

    For more information, see in the
    :class:`~kivymd.theming.ThemableBehavior` and
    :class:`~kivy.uix.boxlayout.BoxLayout` classes documentation.
    """

    color = ColorProperty()
    """
    Divider color in (r, g, b, a) or string format.

    :attr:`color` is a :class:`~kivy.properties.ColorProperty`
    and defaults to `None`.
    """

    divider_width = NumericProperty(dp(1))
    """
    Divider width.

    :attr:`divider_width` is an :class:`~kivy.properties.NumericProperty`
    and defaults to `dp(1)`.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.on_orientation)

    def on_orientation(self, *args) -> None:
        """Fired when the values of :attr:`orientation` change."""

        if self.orientation == "vertical":
            self.size_hint_x = None
            self.width = (
                self.divider_width
            )
        elif self.orientation == "horizontal":
            self.size_hint_y = None
            self.height = (
                self.divider_width
            )