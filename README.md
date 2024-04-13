# USR5637

Python 3 code for USR5637 dial-up modem, connected to phone line, Raspberry Pi 4 and a home router.  

## What it does  
1. Sets up the modem to wait for a phone call  
2. After ~2 rings call is answered and an audio '.wav' file is played
3. Beep signal is played  
4. Voice recording is started and saved to a '.vaw' file   


Note: Code work but has issues, e.g.: 
- it takes too long from playing audio to the beep signal  
- when caller hangs up after recording the message, this is not detected and keeps recording until time-out  


Code adapted from various Python 2 [@pradeesi](https://github.com/pradeesi) repositories.