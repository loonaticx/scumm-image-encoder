import sys
import Image
import traceback
from sie_util import getQWord, getWordLE, arrayToInt, getByte, byteToBits, ImageContainer, getDWord

outfilename = "output"
outfiletype = "png"

HORIZONTAL = 0
VERTICAL = 1

DRAWPIX = 0
READPAL = 2
READVAL = 3
SUBVAR = 6
NEGVAR = 7

INCPAL4 = 0
INCPAL3 = 1
INCPAL2 = 2
INCPAL1 = 3
READ8BITS = 4
DECPAL1 = 5
DECPAL2 = 6
DECPAL3 = 7

def getDimensions(rmhdfile):
    rmhd = file(rmhdfile, 'rb')
    getQWord(rmhd, 0)
    width = getWordLE(rmhd, 0)
    height = getWordLE(rmhd, 0)
    rmhd.close()
    return arrayToInt(width), arrayToInt(height)

def getPalette(palfile):
    palf = file(palfile, 'rb')
    header = getQWord(palf)
    pal = []
    # Don't try interpreting it as RGB tuples, PIL will understand.
    [pal.append( arrayToInt(getByte(palf, 0)) ) for i in range(768)]
    palf.close()
    return pal

# Works in custom-made image
def doUncompressed(smap, img, limit, stripNum):
    ##print "In uncompressed"
    xCounter = 0
    yCounter = 0

    while smap.tell() < limit:
        currPalIndex = arrayToInt(getByte(smap,0))
        img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
        xCounter += 1
        if xCounter >= 8:
            xCounter = 0
            yCounter += 1
            # This bit makes sure we don't go past the image's boundaries
            # (which can happen because a byte requires 8 bits but the
            # image may not need all those bits)
            if yCounter >= img.height:
                break

# Should work now
def doMethodOne(smap, img, limit, stripNum, paramSub, rendDir):
    ##print "In method one"
    xCounter = 0
    yCounter = 0
    bitAcc = 0 # Bit accumulator
    contReadingPal = False
    readCount = 0
    iSubVar = 1

    # Get first (top-left) colour/palette index
    currPalIndex = arrayToInt(getByte(smap, 0))
    ##print "initial pal index is " + str(currPalIndex)
    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
    # Move to next pixel
    if rendDir == HORIZONTAL:
        xCounter += 1
    else:
        ##print "In VERTICAL style"
        yCounter += 1
    ##print "put first pixel"


    while smap.tell() < limit and \
    ((rendDir == HORIZONTAL and yCounter < img.height) or
     (rendDir == VERTICAL and xCounter < 8)):
        thisByte = byteToBits(getByte(smap, 0), LE=1)

        # For each bit
        for b in thisByte:
            # Reading a palette index
            if contReadingPal:
                bitAcc += (b << readCount) # compensates for reading it in reverse
                readCount += 1
                # Finished reading palette index number
                if readCount == paramSub:
                    currPalIndex = bitAcc
                    ##print "Read new palette index, now " + str(currPalIndex)
                    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                    iSubVar = 1 # set subvar
                    # Move to next pixel
                    if rendDir == HORIZONTAL:
                        xCounter += 1
                        if xCounter >= 8:
                            xCounter = 0
                            yCounter += 1
                            if yCounter >= img.height:
                                break
                    else:
                        yCounter += 1
                        if yCounter >= img.height:
                            yCounter = 0
                            xCounter += 1
                            if xCounter >= 8:
                                break
                    ##print "put pixel"
                    contReadingPal = False
                    readCount = 0
                    bitAcc = 0

            elif b == 1:
                bitAcc = bitAcc << 1
                bitAcc += 1
                if bitAcc == NEGVAR:
                    iSubVar = ~iSubVar + 1 # convert -1 to 1 and vice versa
                    currPalIndex -= iSubVar
                    bitAcc = 0
                    # Place pixel
                    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                    # Move to next pixel
                    if rendDir == HORIZONTAL:
                        xCounter += 1
                        if xCounter >= 8:
                            xCounter = 0
                            yCounter += 1
                            if yCounter >= img.height:
                                break
                    else:
                        yCounter += 1
                        if yCounter >= img.height:
                            yCounter = 0
                            xCounter += 1
                            if xCounter >= 8:
                                break

            # Place pixel / end (and execute) a command
            elif b == 0:
                bitAcc = bitAcc << 1 # Do this so we get proper value for checking READPAL
                if bitAcc == READPAL:
                    contReadingPal = True
                    bitAcc = 0
                    # Don't place the pixel until we get the new palette index
                    continue
                elif bitAcc == SUBVAR:
                    currPalIndex -= iSubVar
                    bitAcc = 0
                # Place pixel
                img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                # Move to next pixel
                if rendDir == HORIZONTAL:
                    xCounter += 1
                    if xCounter >= 8:
                        xCounter = 0
                        yCounter += 1
                        if yCounter >= img.height:
                            break
                else:
                    yCounter += 1
                    if yCounter >= img.height:
                        yCounter = 0
                        xCounter += 1
                        if xCounter >= 8:
                            break
                ##print "put pixel"

# Should work now
def doMethodTwo(smap, img, limit, stripNum, paramSub, pal):
    ##print "In method two"
    xCounter = 0
    yCounter = 0
    bitAcc = 0 # Bit accumulator
    contReadingPal = False
    contReadingNumPix = False
    contReadingDecom = False
    readCount = 0

    # Get first (top-left) colour/palette index
    currPalIndex = arrayToInt(getByte(smap, 0))
    ##print "initial pal index is " + str(currPalIndex)
    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
    # Move to next pixel
    xCounter += 1
    ##print "put first pixel"


    while smap.tell() < limit and yCounter < img.height:
    ##while smap.tell() < limit:
        thisByte = byteToBits(getByte(smap, 0), LE=1)

        # For each bit
        for b in thisByte:
            # Reading a palette index
            if contReadingPal:
                bitAcc += (b << readCount)
                readCount += 1
                # Finished reading palette index number
                if readCount == paramSub:
                    currPalIndex = bitAcc
                    ##print "Read new palette index, now " + str(currPalIndex)
                    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                    # Move to next pixel
                    xCounter += 1
                    if xCounter >= 8:
                        xCounter = 0
                        yCounter += 1
                        if yCounter >= img.height:
                                break
                    ##print "put pixel"
                    contReadingPal = False
                    readCount = 0
                    bitAcc = 0

            elif contReadingNumPix:
                bitAcc += (b << readCount)
                readCount += 1
                if readCount == 8:
                    for i in range(bitAcc):
                        img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                        xCounter += 1
                        if xCounter >= 8:
                            xCounter = 0
                            yCounter += 1
                            if yCounter >= img.height:
                                break
                        ##print "put pixel"
                    contReadingNumPix = False
                    readCount = 0
                    bitAcc = 0


            elif contReadingDecom:
                bitAcc += (b << readCount)
                ##print bitAcc
                readCount += 1 # how many bits it has read
                if readCount == 3:
                    # Serge's doc seems to have decrement and increments
                    # mixed up - hence contradictary names
                    if bitAcc == INCPAL4:
                        currPalIndex -= 4
                    elif bitAcc == INCPAL3:
                        currPalIndex -= 3
                    elif bitAcc == INCPAL2:
                        currPalIndex -= 2
                    elif bitAcc == INCPAL1:
                        currPalIndex -= 1
                    elif bitAcc == READ8BITS:
                        contReadingNumPix = True
                        bitAcc = 0
                        readCount = 0
                        contReadingDecom = False
                        continue
                    elif bitAcc == DECPAL1:
                        currPalIndex += 1
                    elif bitAcc == DECPAL2:
                        currPalIndex += 2
                    elif bitAcc == DECPAL3:
                        currPalIndex += 3
                    ##print "new currPalIndex is " + str(currPalIndex)
                    # Place pixel
                    img.img[(stripNum * 8 + xCounter) + (yCounter * img.width)] = currPalIndex
                    # Move to next pixel
                    xCounter += 1
                    if xCounter >= 8:
                        xCounter = 0
                        yCounter += 1
                        if yCounter >= img.height:
                            break
                    ##print "put pixel"
                    bitAcc = 0
                    readCount = 0
                    contReadingDecom = False

            elif b == 1:
                bitAcc = bitAcc << 1
                bitAcc += 1
                if bitAcc == READVAL:
                    contReadingDecom = True
                    bitAcc = 0

            # Place pixel / end (and execute) a command
            elif b == 0:
                bitAcc = bitAcc << 1 # Do this so we get proper value for checking READPAL
                if bitAcc == READPAL:
                    contReadingPal = True
                    bitAcc = 0
                    # Don't place the pixel until we get the new palette index
                    continue
                # Place pixel
                x_index = (stripNum * 8 + xCounter)
                y_index = (yCounter * img.width)
                final_index = x_index + y_index
                # This seems to occur in Sam 'n' Max room 2. The final image seems to be alright
                #  if we ignore these pixels.
                if final_index >= len(img.img):
                    print "x_index + y_index = %s, which is outside the image (max: %s)." % (final_index, len(img.img))
                else:
                    img.img[x_index + y_index] = currPalIndex
                # Move to next pixel
                xCounter += 1
                if xCounter >= 8:
                    xCounter = 0
                    yCounter += 1
                    if yCounter >= img.height:
                        break
                ##print "put pixel"

def decodeImage(lflf):
    print "Reading dimensions from RMHD..."
    # Get dimensions from RMHD file and initialise an image container
    width, height = getDimensions()
    print width, height
    img = ImageContainer(width, height)

    print "Reading palette from CLUT..."
    # Get the palette
    pal = getPalette()

    # Load pixelmap data
    #destpath = os.path.join("008_RMIM", "001_IM00")
    #os.chdir(os.path.join(os.getcwd(), destpath))
    smap = file(smapfile, 'rb')

    # Do these things so we know the size of the last strip
    limit = 0
    header = getDWord(smap, 0) # not used
    blocksize = arrayToInt(getDWord(smap, 0))

    print "Retrieving strip offsets from SMAP..."
    # Get strip offsets
    numStrips = width/8
    stripOffsets = []
    [stripOffsets.append(arrayToInt(getDWordLE(smap, 0)))
         for dummyvar in range(numStrips)]

    print "Reading strips from SMAP... "
    # For reach strip
    for stripnum, s in enumerate(stripOffsets):
        smap.seek(s, 0)
        compID = arrayToInt(getByte(smap,0))
        # Default variables (based on uncompressed settings)
        compMethod = 0 # 0 will also stand for uncompressed
        paramSub = 0
        trans = False
        rendDir = HORIZONTAL

        ##print compID
        # Determine compression type
        if compID == 0x01:
            # Values are already initialised to uncompressed method settings
            pass
        # Method 1 variations
        elif compID >= 0x0E and compID <= 0x12:
            paramSub = compID - 0x0A
            rendDir = VERTICAL
            compMethod = 1
        elif compID >= 0x18 and compID <= 0x1C:
            paramSub = compID - 0x14
            compMethod = 1
        elif compID >= 0x22 and compID <= 0x26:
            paramSub = compID - 0x1E
            rendDir = VERTICAL
            trans = True
            compMethod = 1
        elif compID >= 0x2C and compID <= 0x30:
            paramSub = compID - 0x28
            trans = True
            compMethod = 1
        # Method 2 variations
        elif compID >= 0x40 and compID <= 0x44:
            paramSub = compID - 0x3C
            compMethod = 2
        elif compID >= 0x54 and compID <= 0x58:
            paramSub = compID - 0x50 # Serge's thing says 0x51
            trans = True
            compMethod = 2
        elif compID >= 0x68 and compID <= 0x6C:
            paramSub = compID - 0x64
            trans = True
            compMethod = 2
        elif compID >= 0x7C and compID <= 0x80:
            paramSub = compID - 0x78
            compMethod = 2
        else:
            print "Unknown compression method for strip " + str(compID)
            smap.close()
            sys.exit(1)

        if stripnum+1 == len(stripOffsets): # is it the last strip?
            limit = blocksize
        else:
            limit = stripOffsets[stripnum+1]
        # Try/except is for debugging - will show however much image we've decoded
        try:
            if compMethod == 0:
                print "Processing uncompresed strip"
                doUncompressed(smap, img, limit, stripnum)
            elif compMethod == 1:
                print "Processing strip with method one"
                doMethodOne(smap, img, limit, stripnum, paramSub, rendDir)
            elif compMethod == 2:
                print "Processing strip with method two"
                doMethodTwo(smap, img, limit, stripnum, paramSub, pal)
        except Exception, e:
            traceback.print_exc()
            print "ERROR: %s" % e
            print "An error occured - attempting to show incomplete image."
            im = Image.new('P', (img.width, img.height) )
            im.putpalette(pal)
            im.putdata(img.img)
            ##im.fromstring(img.img.tostring())
            im.show()
            smap.close()
            sys.exit(1)

    smap.close()

    print "Creating image file..."
    # Create our new image!
    im = Image.new('P', (img.width, img.height) )
    im.putpalette(pal)
    im.putdata(img.img)
    im.save(outfilename + "." + outfiletype, outfiletype)
