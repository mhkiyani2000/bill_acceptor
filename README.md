# Bill Acceptor

## A virtual RS-232 Bill Acceptor
Emulate an RS-232 bill acceptor in software.

### Requirements

 - Python 2.7
 - Null modem emulation


### Getting Started

- 	Make sure that Kivy and TFT Touchscreen Driver has installed successfully on your Raspberry Pi

-	Install socat package
	apt-get install socat
-	Run socat to emulate virtual serial port
	socat -d -d pty,raw,echo=0 pty,raw,echo=0
	Then it will say that 2 virtual serial port is assigned with 
		/dev/pts/2
		/dev/pts/3
		(NOTE : number will be changed)
-	Run main APP(bill_acceptor) with given port name above
	python main.py /dev/pts/2
-	Go to the soft-bill-master directory and run main.py
	python main.py /dev/pts/3
	
- key map:
	1 : 1$	
	2 : 2$	
	3 : 5$	
	4 : 10$	
	5 : 20$	
	6 : 50$	
	7 : 100$	
                    

