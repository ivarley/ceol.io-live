# 013 Simplified Registration & Login

I want to make it a lot simpler to register and log in.

- Do away with username; email can be the username. (I'll email everyone who's already got an account to let them know of the change.)
- Change the button on the home page, and the link in the hamburger menu, to "Login Or Register"
- On /login, just ask for email, with a "Next" button.
  - If their email is found for an existing user, expand to show a password field allowing login.
    - Or if they don't have a password, immediately send them a "Click this link to log in" link to their email that allows them to log in directly, and brings them to a screen that says "Set a password for easier login next time (optional): ".
  - If their email is not found, add their email as a new user immediately and send a verify email to them immediately asking to verify their email. First time users aren't logged in until they've done this.
    - Show a "Set a password for easier login next time (optional)" field next and let them create a password if they want to.
    - BUT, if they don't create a password, they are still considered logged in if they verified their email.
