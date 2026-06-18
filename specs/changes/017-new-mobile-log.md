# 017 New Mobile Log

The current logging UI works well enough on desktop but it's a pain to use on mobile devices. So we are going to create an entirely new UI on mobile. Let's make this a whole new page so as not to fight with any of the existing code. Anything that's truly shared between the two views should be factored out into a shared js / css / html file that both desktop and mobile views can include; that way we're consciously sharing rather than depending on what was there before.

The first change is that there's a portion of the screen that's "docked" to both the top and bottom of the screen. At the top, the session name and date, and the tunes / players tabs - that's in a container that's docked to the top of the screen below the top menu. 

At the bottom of the screen, there's a docked view (taking up about half of the vertical real estate) showing the tune set you're currenty editing. By default, this area has an input box into which you can type a tune name. As you type, 

In the middle of the screen is the scrollable tune list (which is always in the "view" mode of the current UI, excep that tapping a set (the ) selects the entire set