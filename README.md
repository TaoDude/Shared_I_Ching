# Shared_I_Ching
Public code from the Sci-Fi your Pi Design competition I Ching Hexagrams entry.
This project contains elements of software produced by the vendors of the PiFaceCAD add-on board for the Raspbery Pi.
The vendors of the board have applied the GPL V3 licence to their code, so I have passed that licence on to anyone 
who wishes to make use of my code.

Please note that the IR element is untested.
If you don't intend to use it, it is prabably best to comment the section out or delete it.

The code expects a file called ichinglircrc in /usr/share/doc/scifipi-i-ching so that the lircrc file for other
applications can be left unaltered.  If you are adapting the code for a different use, you will need to modify the line:

lircrc="/usr/share/doc/scifipi-i-ching/ichinglircrc")

to point at your application's lircrc file.
