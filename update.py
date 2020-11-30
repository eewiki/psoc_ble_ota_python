#!env/bin/python

from bluepy import btle
import cydfu
import crcmod
import sys
import threading
import queue


class Delegate(btle.DefaultDelegate):
    def __init__(self):
        super().__init__()
        self.handle = None
        self.data = None

    def handleNotification(self, cHandle, data):
        self.handle = cHandle
        self.data = data


class ScannerUI():
    _choiceWidth = 6
    _nameWidth = 16
    _macAddrWidth = 17
    _rssiWidth = 7

    def __init__(self):
        self._userInput = queue.Queue()
        self._inputThread = threading.Thread()
        self.reset()

    def reset(self):
        """Reset the UI. 
        
        For example, if the selected device failed to connect and the user must
        choose again.
        """
        # Reset state data
        self.devCount = 0
        self._userSelection = None
        self._errMsg = ''

    def update(self, devices):
        """Update the UI by including the supplied devices in the table"""
        if devices == []:
            return

        # Remove the prompt and move cursor to just below table
        self._moveCursorLeft(999) # Move cursor to beginning of line (prompt)
        self._clearCursorToEnd() # Clear the line (prompt)
        self._moveCursorUp() # Move cursor up to add table entry

        for device in devices:
            self.devCount += 1
            self._addDevice(device) # Display the new device in the table

        # Re-display the prompt
        print()
        self._displayPrompt()

    # TODO: Make scaleable. Add options for abort, refresh, etc. 
    @property
    def userSelection(self):
        """Get, validate, and cache the user's selection."""
        if self._userSelection == None: # If the user has not yet made a valid selection
            if not self._userInput.empty(): # If the user has provided some input
                # Remove user input from queue
                selection = self._userInput.get() 
                
                # If user chose to quit...
                if (selection == 'q') or (selection == 'Q'):
                    raise SystemExit
                
                # Validate the user's input
                try:
                    selection = int(selection)
                except Exception:
                    self._errMsg = f"Choice \"{selection}\" not valid. "
                else:
                    if (selection < 1) or (selection > self.devCount):
                        self._errMsg = f"Device {selection} is not on the list. "
                    else:
                        self._userSelection = selection
                        self._errMsg = ''

                # If user input was invalid, re-print the prompt
                if (self._errMsg != ''):
                    self._moveCursorUp()
                    self._moveCursorLeft(999)
                    self._clearCursorToEnd()
                    self._displayPrompt()

        return self._userSelection 

    def printHeader(self):
        """Display the table header."""
        print(
            f" {'Choice':^{self._choiceWidth}} |"
            f" {'Device Name':^{self._nameWidth}} |"
            f" {'MAC ADDRESS':^{self._macAddrWidth}} |"
            f" {'RSSI':^{self._rssiWidth}} "
        )
        print('-' * (2 + self._choiceWidth)
            + '+' + '-' * (2 + self._nameWidth)
            + '+' + '-' * (2 + self._macAddrWidth)
            + '+' + '-' * (2 + self._rssiWidth)
        )
        print() 

    def _addDevice(self, device):
        """Display device the info as a table row."""
        devName = device.getValueText(9)
        if devName == None:
            devName = "<No Name>"

        print(
            f" {self.devCount:^{self._choiceWidth}} |"
            f" {devName[:self._nameWidth]:<{self._nameWidth}} |"
            f" {device.addr:^{self._macAddrWidth}} |"
            f" {f'{device.rssi} dB':^{self._rssiWidth}} "
        )

    def _displayPrompt(self):
        print(self._errMsg, end='')
        print("Choose a device to update [q to quit]: ", end='', flush=True)
        
        # If there is no thread to get user input running, start one
        if not self._inputThread.isAlive():
            self._inputThread = threading.Thread(target=self._getUserInput)
            self._inputThread.start()

    def _getUserInput(self):
        self._userInput.put(input())

    def _moveCursorLeft(self, count=1):
        print(f"\x1B[{count}D", end='')

    def _moveCursorUp(self, count=1):
        print(f"\x1B[{count}A", end='')

    def _clearCursorToEnd(self):
        print("\x1B[K", end='')


class Target(btle.Peripheral):

    def updateFirmware(self, app, maxDataLength=512):
        crc32cFunc = crcmod.predefined.mkCrcFun('crc-32c')
        hostCmd = cydfu.DFUProtocol(self)

        # Send the Enter DFU command
        print("Starting DFU operation...")
        hostCmd.enterDFU(app.productID)
        print(f"> Product ID: 0x{app.productID:08X}\n")

        # Set Application Metadata
        hostCmd.setApplicationMetadata(app.appID, app.startAddr, app.length)
        print(f"Application {app.appID} is {app.length} bytes long. Will begin writing at memory address 0x{app.startAddr:08X}.\n")

        # Send row data to target
        print("Sending Data...")
        while True:
            try:
                rowAddr, rowData = app.getNextRow()
            except Exception:
                break

            # Calculate the CRC-32C checksum of the row data
            crc = crc32cFunc(rowData)

            # Break the row data into smaller chunks of size maxDataLength
            rowData = [rowData[i:i+maxDataLength] for i in range(0, len(rowData), maxDataLength)]

            # Send all but the last chunk using the Send Data command
            for chunk in rowData[:-1]:
                hostCmd.sendData(chunk)

            # Send the last chunk using the Program Data command
            hostCmd.programData(rowAddr, crc, rowData[-1])
            print(f"> Sent Data Row {app.currRow}/{app.numRows}")

        print("Finished sending application to target.\n")

        # Send Verify Application command
        print("Verifying Application...")
        result = hostCmd.verifyApplication(fwImg.appID)
        if result == 1:
            print("> The application is valid!")
        else:
            print("> The application is NOT valid.")

        # Send the Exit DFU command
        print("Ending DFU operation.")
        hostCmd.exitDFU()


    def eraseFirmware(self, appNum):
        # TODO Implement
        pass


if __name__ == '__main__':
    usageStatement = "Usage: update.py applicaion_file [target_MAC_address]"
    
    # Check the command line arguments
    if (len(sys.argv[1:]) == 0) or (len(sys.argv[1:]) > 2):
        print(usageStatement)
        raise SystemExit

    # If 1 or 2 command line arguments were provided, process the first one
    try:
        fwImg = cydfu.Application(sys.argv[1])    
    except FileNotFoundError:
        print(f"{sys.argv[1]} does not exist.")
        raise SystemExit
    except cydfu.InvalidFileType:
        print(usageStatement + '\n')
        raise
    except cydfu.InvaildApplicationFile:
        raise
    except Exception:
        print(usageStatement + '\n')
        raise 
    
    print(f"Successfully opened application image file \"{sys.argv[1]}\"")
    print(f"> File Version: 0x{fwImg.fileVersion:02x}")
    print(f"> App ID: {fwImg.appID}")
    print()
    
    # If the optional second cmd line argument was provided, try to connect
    target = None
    if len(sys.argv[1:]) == 2:
        try:
            target = Target(sys.argv[2]).withDelegate(Delegate())
        except Exception as e:
            print(e.args[0])
            raise SystemExit

    if (target == None):
        # Create scanner and scanner user interface objects
        scanner = btle.Scanner()
        scannerUI = ScannerUI()

        while (target == None):
            # Forget preveously discovered devices
            scanner.clear()
            scannerUI.reset()

            # Start the scanner
            scanner.start()
            print("Scanning for devices...\n")

            # Continuously scan for devices while waiting for the user to choose one
            scannerUI.printHeader() 
            while scannerUI.userSelection == None:
                scannerUI.update(list(scanner.getDevices())[scannerUI.devCount:])
                scanner.process(1)

            # Stop the scanner
            try:
                scanner.stop()
            except Exception:
                print("Error stopping scanner.")

            # Retrieve the selected device
            device = list(scanner.getDevices())[scannerUI.userSelection-1]

            # Try to connect to the device
            try:
                target = Target(device).withDelegate(Delegate())
            except Exception:
                print(f"Could not connect to device {device.addr}.")


    target.updateFirmware(fwImg)
    fwImg.close()

    # TODO Make this more robust
    try:
        target.disconnect()
    except Exception:
        pass
    finally:
        print( "Disconnected from DFU Device." )
