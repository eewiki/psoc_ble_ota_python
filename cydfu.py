import struct


CYPRESS_GATT_SERVICE_BOOTLOADER_UUID = "00060000-F8CE-11E4-ABF4-0002A5D5C51B"
CYPRESS_GATT_CHARACTERISTIC_COMMAND_UUID = "00060001-F8CE-11E4-ABF4-0002A5D5C51B"


class HostError(Exception):
    pass

class DFUError(Exception):
    pass

class DFUErrorVerify(DFUError):
    pass

class DFUErrorLength(DFUError):
    pass

class DFUErrorData(DFUError):
    pass

class DFUErrorCmd(DFUError):
    pass

class DFUErrorChecksum(DFUError):
    pass

class DFUErrorRow(DFUError):
    pass

class DFUErrorRowAccess(DFUError):
    pass

class DFUErrorUnknown(DFUError):
    pass

class UnexpectedError(Exception):
    pass
    
class InvalidFileType(Exception):
    pass

class InvalidApplicationFile(Exception):
    pass

class DFUProtocol:
    """Device Firmware Update Host Command/Response Protocol"""
    _START_OF_PACKET                 = b'\x01'
    _END_OF_PACKET                   = b'\x17'

    _CMD_ENTER_DFU                   = b'\x38'
    _CMD_SYNC_DFU                    = b'\x35'
    _CMD_EXIT_DFU                    = b'\x3B'

    _CMD_SEND_DATA                   = b'\x37'
    _CMD_SEND_DATA_WITHOUT_RESPONSE  = b'\x47'
    _CMD_PROGRAM_DATA                = b'\x49'
    _CMD_VERIFY_DATA                 = b'\x4A'
    _CMD_ERASE_DATA                  = b'\x44'

    _CMD_VERIFY_APPLICATION          = b'\x31'
    _CMD_SET_APPLICATION_METADATA    = b'\x4C'
    _CMD_GET_METADATA                = b'\x3C'
    _CMD_SET_EIVECTOR                = b'\x4D'

    _DFU_STATUS_CODE = {
            b'\x00': None,
            b'\x02': DFUErrorVerify,
            b'\x03': DFUErrorLength,
            b'\x04': DFUErrorData,
            b'\x05': DFUErrorCmd,
            b'\x08': DFUErrorChecksum,
            b'\x0A': DFUErrorRow,
            b'\x0B': DFUErrorRowAccess,
            b'\x0F': DFUErrorUnknown,
    }


    def __init__(self, dfuTarget):
        # Get the bootloader command characteristic (should be the only one...)
        self._dfuCmdChar = dfuTarget.getCharacteristics(uuid=CYPRESS_GATT_CHARACTERISTIC_COMMAND_UUID)[0]

        # Get the Client Characteristic Configuration Descriptor (CCCD)
        self._dfuCCCD = self._dfuCmdChar.getDescriptors(forUUID=0x2902)[0]
        
        # Enable notifications from the Bootloader service
        self._enableNotifications(self._dfuCCCD)


    def enterDFU(self, productID = 0):
        """Begin a DFU operation"""
        # Create the packet payload
        payload = struct.pack("<I", productID)
        
        # Send the Enter DFU command and get the response
        respData = self._sendCommandGetResponse(self._CMD_ENTER_DFU, payload, 2)

        # Parse reponse packet payload and print data fields
        jtagID, deviceRev, dfuSdkVer = struct.unpack("<IBI", respData[:5] + b'\x00' + respData[5:])
        print("Enter DFU successful.")
        print(f"> JTAG ID: 0x{jtagID:08x}")
        print(f"> Device Revision 0x{deviceRev:02x}")
        print(f"> DFU SDK Version 0x{dfuSdkVer:08x}")

    
    def syncDFU(self):
        """Resets the DFU to a known state, making it ready to accept a new command."""
        # Create and send the Sync DFU command packet
        packet = self._createCmdPacket(self._CMD_SYNC_DFU)
        self._sendPacket(packet)
        
        # This command is not acknowledged


    def exitDFU(self):
        """Ends the DFU operation"""
        # Create and send the Exit DFU command packet
        packet = self._createCmdPacket(self._CMD_EXIT_DFU)
        self._sendPacket(packet)

        # This command is not acknowledged


    def sendData(self, data):
        """Transfers a block of data to the DFU module."""
        # Send the Send Command command and get the response from the target
        self._sendCommandGetResponse(self._CMD_SEND_DATA, data, 2)


    def sendDataWithoutResponse(self, data):
        """Same as the sendData command, except that no response is generated."""
        # Create and send the Send Data Without Response command packet
        packet = self._createCmdPacket(self._CMD_SEND_DATA_WITHOUT_RESPONSE, data)
        self._sendPacket(packet)

        # This command is not acknowledged


    def programData(self, rowAddr, rowDataChecksum, data):
        """Writes data to one row of the device internal flash or page of external NVM."""
        # Create the packet payload
        payload = struct.pack("<II", rowAddr, rowDataChecksum) + data

        # Send the Program Data command and get the response from the target
        self._sendCommandGetResponse(self._CMD_PROGRAM_DATA, payload, 2)
        

    def verifyData(self, rowAddr, rowDataChecksum, data):
        """Compares data to one row of the device internal flash or page of SMIF."""
        # Create the packet payload
        payload = struct.pack("<II", rowAddr, rowDataChecksum) + data
        
        # Create and send the Verify Data command packet
        self._sendCommandGetResponse(self._CMD_VERIFY_DATA, payload)
        

    def eraseData(self, rowAddr):
        """Erases the contents of the specified internal flash row or SMIF page."""
        # Create the packet payload
        payload = struct.pack("<I", rowAddr)
        
        # Create and send the Erase Data command packet
        self._sendCommandGetResponse(self._CMD_ERASE_DATA, payload)

        
    def verifyApplication(self, appNum):
        """Reports whether the checksum for the application in flash or external NVM is valid."""
        # Create the packet payload
        payload = struct.pack("<B", appNum)
        
        # Send the Verify Application command and get the response from the target
        respData = self._sendCommandGetResponse(self._CMD_VERIFY_APPLICATION, payload, 2)

        # Parse the response packet payload and return the result of the query
        return struct.unpack("<B", respData)[0]


    def setApplicationMetadata(self, appNum, appStartAddr, appLength):
        """Set a given application's metadata."""
        # Create the packet payload
        payload = struct.pack("<BII", appNum, appStartAddr, appLength)

        # Send the Set Application Metadata command and get the response from the target
        self._sendCommandGetResponse(self._CMD_SET_APPLICATION_METADATA, payload, 2)

    
    def getMetadata(self, fromRowOffset, toRowOffset):
        """Reports selected metadata bytes."""
        # Create the packet payload
        payload = struct.pack("<II", fromRowOffset, toRowOffset)

        # Create and send the Get Metadata command packet
        self._sendCommandGetResponse(self._CMD_GET_METADATA, payload)


    def setEIVector(self, vector):
        """Sets an encrypted initialization vector (EIV). CURRENTLY NOT IMPLEMENTED"""
        pass


    def _calcChecksum_2sComplement_16bit(self, data):
        # Check input parameter
        if not isinstance(data, bytes):
            raise HostError("data must be a bytes object")

        # Calculate the 16-bit 2's complement checksum
        cs = 0
        for b in data:
            cs = cs + b
        
        return (-cs & 0xFFFF)


    def _checkStatusCode(self, code):
        # get exception to raise
        try:
            ex = self._DFU_STATUS_CODE[code]
        except KeyError:
            raise UnexpectedError("The target responded with an undefined status code")
        
        # raise the exception if one was provided
        if ex:
            raise ex()


    def _createCmdPacket(self, cmd, payload=b''):
        # Check input parameters
        if (not isinstance(cmd, bytes)) or (len(cmd) != 1):
            raise HostError("cmd must be a bytes object with a length of 1")

        if not isinstance(payload, bytes):
            raise HostError("payload must be a bytes object")

        # Create command packet according to Figure 32 of AN213924
        payloadLength = len(payload)
        packet = struct.pack(f"<ccH{payloadLength}s", self._START_OF_PACKET, cmd, payloadLength, payload)
        return packet + struct.pack("<Hc", self._calcChecksum_2sComplement_16bit(packet), self._END_OF_PACKET)


    def _enableNotifications(self, cccd):
        # Set the enable notifications bit in the CCCD's value
        # Must send write request *with* response
        cccd.write(b'\x01\x00', withResponse=True)

        # Check the value of the CCCD to ensure notifications are enabled
        cccdValue = cccd.read()
        if cccdValue != b'\x01\x00':
            raise HostError("Failed to enable Bootloader service notifications.")


    def _getResponse(self, packet):
        # Attempt to unpack the response packet according to Figure 33 of AN213924
        try:
            startByte, statusCode, dataLength = struct.unpack("<ccH", packet[0:4])
            payload, checksum, endByte = struct.unpack(f"<{dataLength}sHc", packet[4:])
        except:
            raise HostError("The response packet is malformed")

        if (startByte != self._START_OF_PACKET) or (endByte != self._END_OF_PACKET):
            raise HostError("The response packet is malformed")

        # Verify packet checksum
        if self._calcChecksum_2sComplement_16bit(packet[:-3]) != checksum:
            raise HostError("The response packet is currupted")

        return [statusCode, payload]


    def _sendCommandGetResponse(self, cmd, payload=b'', timeout=1):
        # Create the command packet 
        packet = self._createCmdPacket(cmd, payload)

        # Send packet to target
        self._sendPacket(packet)

        # Wait for response from the target
        if not self._waitForResponse(timeout):
            raise HostError(f"Notification from handle {self._dfuCmdChar.getHandle()} not received")
        
        # Extract the status code and payload of the target's response packet
        statusCode, respData = self._getResponse(self._dfuCmdChar.peripheral.delegate.data)

        # Check status code
        self._checkStatusCode(statusCode)

        return respData


    def _sendPacket(self, packet, maxLen=20):
        # Send the packet in maxLen increments
        packet = [packet[i:i+maxLen] for i in range(0, len(packet), maxLen)]
        for p in packet:
            self._dfuCmdChar.write(p)


    def _waitForResponse(self, timeout=1):
        """timeout is in seconds"""
        # Block until either a notification is received from the target or the timeout elapses
        if not self._dfuCmdChar.peripheral.waitForNotifications(timeout):
            return False

        # If received notification is not from the DFU characteristic
        while self._dfuCmdChar.peripheral.delegate.handle != self._dfuCmdChar.getHandle():
            return False

        # TODO handle receiving notifications from multiple characteristics
        return True


class Application:
    """Opens and parses the cyacd2 file containing the downloadable application data"""

    def __init__(self, cyacd2_file):
        """Opens the cyacd2 file provided. Retrieves file info from header and 
           application data from the APPDATA row"""
        # Ensure the file name has the ".cyacd2" extension
        if not cyacd2_file.endswith(".cyacd2"):
            raise InvalidFileType("Expected an application file with the extension '.cyadc2'")

        # Open the cyacd2 file
        self._app = open(cyacd2_file, 'r')

        # Count the number of lines in the file
        self.numRows = self._getNumLines()

        # Read and print the header info
        self.getHeader()
        self.numRows -= 1 # not a data row

        # Read and print application verification information
        self.getAppInfo()
        self.numRows -= 1 # not a data row

        # TODO Handle files with an EIV (Encryption Initial Vector) row

        # Initialize currRow counter
        self.currRow = 0

    def _getNumLines(self):
        # Save the current stream position
        prevPos = self._app.tell()

        # Seek to the beginning of the file and count the number of lines
        self._app.seek(0)
        lineCount = 0
        while self._app.readline():
            lineCount += 1

        # Return to the original stream position
        self._app.seek(prevPos)

        return lineCount

    def getHeader(self):
        # Read the header 
        header = next(self._app).strip()
        header = bytes.fromhex(header)

        # Verify header length
        if len(header) != 12:
            raise InvalidApplicationFile("Malformed header")

        # Extract fields from header
        header = struct.unpack("<BIBBBI", header)
        self.fileVersion = header[0]
        self.siliconID = header[1]
        self.siliconRevision = header[2]
        self.checksumType = header[3]
        self.appID = header[4]
        self.productID = header[5]

    def getAppInfo(self):
        # Read the application verification information
        appinfo = next(self._app).strip()

        # Separate label from metadata
        appinfo = appinfo.split(':')

        # Verify that the label is valid
        if appinfo[0] != "@APPINFO":
            raise InvalidApplicationFile("Malformed application verification information")

        # Extract fields from metadata
        self.startAddr, self.length = appinfo[1].split(',') # they are big endian
        self.startAddr = int(self.startAddr, 0)
        self.length = int(self.length, 0)

    def getNextRow(self):
        # Read row
        row = next(self._app)

        # Verify row header
        if row[0] != ':':
            raise InvalidApplicationFile("Malformed data row")
        self.currRow += 1

        # Extract row data
        _, row = row.split(':', 1)
        row = row.strip()
        row = bytes.fromhex(row)
        dataLength = len(row) - 4 # 4-byte address + N bytes of data
        rowAddr, rowData = struct.unpack(f"<I{dataLength}s", row)
        return [rowAddr, rowData]

    def close(self):
        self._app.close()


if __name__ == "__main__":
    pass
