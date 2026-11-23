"""Run once, on your own computer, to sign in to Garmin and get the long-lived
tokens the sync uses. It asks for your Garmin email, password and (if you
use it) the two-factor code, then prints one long string. Paste that string
into the private repo as the GARMIN_TOKENS secret. Your password is not
saved anywhere. The tokens last about a year; run this again when the board
says Garmin stopped syncing.

    pip install garminconnect
    python make_tokens.py
"""
import getpass

from garminconnect import Garmin

email = input("Garmin email: ")
password = getpass.getpass("Garmin password: ")
api = Garmin(email=email, password=password, prompt_mfa=lambda: input("Two-factor code: "))
api.login()
print("\nGARMIN_TOKENS (copy all of it):\n")
print(api.garth.dumps())
