# deCainify
Fallout2 executable de-Cainify tool. It replaces 48x48 icon with Tim's face with Vault Boy.

![image](https://github.com/user-attachments/assets/2db0ed0c-7060-4985-a023-8e1cfa025c03)

## Usage in Windows

Download deCainify_gui.exe from Releases.

Select Fallout2.exe (or Fallout2HR.exe or whatever)

![image](https://github.com/user-attachments/assets/d6c8ffe0-e49e-4a7c-8326-0200c26b075c)

And "save as" preferrably with some new file name, such as Fallout2HRdC.exe

If you use sfall (as you most likely are), add the CRC check number to the ddraw.ini ExtraCRC line (remember to remove ";")

## Dependencies
pip install pillow, tkinter, numpy

or

pip install -r requirements.txt

## Why so complicated?

I would not dare to distribute Vault boy icon with the release! Hence, the app locates the smaller scale vb from the exe, upscales it to 48x48, and replaces Tim Cain.

## Disclaimer

Use at your own risk.
