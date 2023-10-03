from trc import TRCData
import time
import copy
import random
from multiprocessing import Process, freeze_support, Queue


import numpy as np
import matplotlib.pyplot as plt


# 1st index is frame number. [1] is frame 1
# 2nd index: [1][0] is the time for that frame
# 2nd index: [1][1] whole frame for all markers
# 3rd index: for specifying which marker. [1][1][0] is for 'Root' marker @ frame 1.
# 1/120  =  0.00833333
# type of a "[1][1][0]" is a tuple of the x, y, and z readings
# type of "[1]" is tuple a time value, and the tuples of the readings (as above) for that frame


def custom_sine_wave(time, amplitude, frequency):
    return amplitude * np.sin(2 * np.pi * frequency * time)

def drifter( inertialFrame: tuple, opticalFrame: tuple, markers: list, amplitude: float, frequency: float, verticalShift: float ):
# Function: takes a partially/fully empty optical TRC frame and fills it with drifted values form the inertial TRC frame.

    index = 0
    for marker in markers:
        if opticalFrame[1][index] == 'N/A':
            opticalFrame[1][index] = (0,0,0)
            # markers[index] = ( marker[0], marker[1] + 1, marker[2])  # increase consecutive inertial frame count.  Used in a later version to model long term drift accumulation.
            opticalFrame[1][index] = addDriftToReading( inertialFrame[1][index],  inertialFrame[0], amplitude, frequency, verticalShift)
            
        index += 1

    return opticalFrame

def addDriftToReading( readingXYZ: tuple, time: float, amplitude: float, frequency: float, verticalShift: float):
    # only need to add drift value to one axis.

    readingXYZ = ( round( readingXYZ[0] + custom_sine_wave(time, amplitude, frequency) + verticalShift, 4), readingXYZ[1], readingXYZ[2] )

    return readingXYZ

def occluder( opticalFrame: tuple, opticalFPS: int, occlusionDuration: float, occlusionNumber: int, markers: list):
    # Purpose: 
    # Occludes group of markers from opticalFrame.
    # Parameters:
    # opticalFrame: occlude random group of markers from this frame.  opticalFPS: to calculate how many frames must be occluded for a group
    # occlusionDuration: How long in seconds a group should be occluded for. occlusionNumber: number of markers to be occluded at a time
    # markers: array of marker objects.

    #PROGRAM LOGIC:
    # case 1: start of program
                    # if all oclCounts = 0 > case 1 (short circuit if found non-zero)
                    # seed first random group
    # case 2: a group is at end of occlusion cycle
                    # seed new random group
    # in both cases: remove optical reading, increasae occluded frame count

    oclFrameTarget = int(opticalFPS * occlusionDuration)  # 'int' might run into problems later
    oclGroupIndexes = []

    programStart = True                # Start of occlusion cycle (or new program run)?
    for marker in markers:
        if marker[2] != 0:
            programStart = False
            break

    if programStart:                   # Yes? Seed first random group
        for _ in range( 0, occlusionNumber ):
            random_num = random.randint(0, len(markers) - 1)
            while random_num in oclGroupIndexes:
                random_num = random.randint(0, len(markers) - 1)
            oclGroupIndexes.append(random_num)

    else:                           # No? Find current random group
        index = 0
        for marker in markers:
            if marker[2] != 0:
                oclGroupIndexes.append(index)
            index += 1

        if markers[oclGroupIndexes[0]][2] == oclFrameTarget:  # occlusion duration reached?
            
            index = 0
            for marker in markers:           # reset occluded frame count for all (and consecutive inertials count, although we don't use it)
                markers[index] = (markers[index][0], 0, 0 )
                index +=1

            oclGroupIndexes = []             # seed new random group
            for _ in range( 0, occlusionNumber ):
                random_num = random.randint(0, len(markers) - 1)
                while random_num in oclGroupIndexes:
                    random_num = random.randint(0, len(markers) - 1)
                oclGroupIndexes.append(random_num)

    # Given a new or pre-existing random group from above, increase ocl count and remove readings
    for markerIndexes in oclGroupIndexes:
        markers[markerIndexes] = (markers[markerIndexes][0], markers[markerIndexes][1], markers[markerIndexes][2] + 1)    # increase occluded frame count
        opticalFrame[1][markerIndexes] = 'N/A'

    # remove consecutive inertial frame count for markers not in ocl group       # Drifter function will increase CIFC count. 
    # count = 0
    # for marker in markers:
    #     if count not in oclGroupIndexes:
    #         marker = (marker[0], 0, marker[2] )
    #     count += 1
    # we do not use consecutive inertial frame count as of now, because we are not tracking longterm drift.

    return opticalFrame

def removeReading(TRCframe: TRCData, groups: list, markersNamesFrameOrder: list):
# Input: TRC frame.  Group: list of strings for the readings that need removing. 

    count = 0
    for names in markersNamesFrameOrder:
        for name in groups:
            if name == names:
                TRCframe[1][count] = 'N/A'
                break
        count = count + 1

    return TRCframe

def createMarkerObjectList(markerNames: list):
# creates a list of objects to track info about each marker. Structure: [0] = markerName, [1] = count of consecutive inertial frames and thus resultant drift to add, [2] = how many optical frames it has been occluded for

    list = []
    for names in markerNames:
        list.append((names,0,0))

    return list

# Fuser:  input takes two queues.  Output: gets a copy of the input TRCData struct to change into the output
# Input:
# inertialQueue: stream of inertial frames. opticalQueue: stream of optical frames.  FPS.  oclSeconds: how long an occlusion lasts.
# numGroupsToOcclude: how many groups to occlude for a given 'round', derived from a percent value.  groupsWithOclCounts: marker groups,
# including the number of frames they've been occluded for.  

    return 

def fuser(inertialQueue: Queue, opticalQueue: Queue, fusedQueue: Queue, opticalFPS: int, oclDuration: float, occlusionNumber: int, 
          markers: list, amplitude: float, frequency: float, verticalShift: float, frameNum: int):

    currFrameCount = 0
    bothQueueGrabCounter = 0
    while currFrameCount < frameNum:

        if bothQueueGrabCounter == 0:   # get optical and inertial

            inertFrame = inertialQueue.get()
            opticFrame = opticalQueue.get()
            occludedOptical = occluder(opticFrame, opticalFPS, oclDuration, occlusionNumber, markers)   
            driftedFused = drifter(inertFrame, occludedOptical, markers, amplitude, frequency, verticalShift)
            fusedQueue.put(driftedFused)
        else:                               # just get inertial, create empty frame to pass to drifter for a complete filling of readings.
            
            inertFrame = inertialQueue.get()
            emptyFrame = copy.deepcopy(inertFrame) # awkward, but because the drifter fills in empty readings with inertial readings, thus we need fully empty TRC frame
            count = 0
            for reading in emptyFrame[1]:
                emptyFrame[1][count] = 'N/A'
                count += 1
            
            driftedFused = drifter( inertFrame, emptyFrame, markers, amplitude, frequency, verticalShift)
            fusedQueue.put(driftedFused)
    
        currFrameCount += 1
        bothQueueGrabCounter =  bothQueueGrabCounter + 1
        if bothQueueGrabCounter == 4:
            bothQueueGrabCounter = 0

    return

def feederFunc( data: TRCData, fps: int, inertialQueue: Queue, opticalQueue: Queue,  opticalSkipFactor: int, frameCount: int ):
# forever feeds TRC frames, from a file that is fully read in, into a queue based on fps. skip factor: if set to 1, reads every frame. If set to 4, sends every 4th frame.

    # interval = 1/fps
    frameNum = -1          # is actually -1 than actual value, to allow for opticalSkipFactor modding to provide first frame as optical
    
    # time1 = (time.monotonic())

    while (frameNum + 1)  < frameCount :

        # time2 = (time.monotonic())

        # while (time2 - time1) < interval:
        #     time2 = (time.monotonic())
        # time1 = time2
         
        frameNum += 1
        
        inertialQueue.put(data[frameNum + 1]) 
        if (frameNum % opticalSkipFactor ) == 0:
            opticalQueue.put(data[frameNum + 1])          # "+ 1" to provide a optical frame for the first reading: 0 % 4 = 0
    return

def writeToOutfile( fusedQueue, inFilePath, outFilePath ):

    inFile = open(inFilePath, 'r')
    outputFile = open(outFilePath, 'w')

    # write header from original file to output file
    for _ in range(6):
        header = inFile.readline()
        outputFile.write(header)
    inFile.close()

    count = 1 
    for _ in range(int(numFrames)):
        frame = fusedQueue.get()
        outputFile.write(str(count))
        outputFile.write("\t")
        outputFile.write(str(frame[0]))
        outputFile.write("\t")
        for readingsTriplet in frame[1]:
            outputFile.write(str(readingsTriplet[0]))
            outputFile.write("\t")
            outputFile.write(str(readingsTriplet[1]))
            outputFile.write("\t")
            outputFile.write(str(readingsTriplet[2]))
            outputFile.write("\t")
        outputFile.write("\n")
        count += 1
    outputFile.close()
    return

def produceOpticalComparisonStats( opticalTRCData, outFilePath, numFrames, numMarkers, opticalSkipFactor: int ):
# because drift was only added in the x axis, error only needs to be calculated in the x-axis

    simulatedHybridTRCData = TRCData()
    simulatedHybridTRCData.load(outFilePath)

    errorValues = []
    errorSum = 0
    
    grabFrameCounter = 0
    currFrame = 1
    
    while currFrame <= numFrames:
        
        if grabFrameCounter == 0:
            currMarker = 0
            while currMarker < numMarkers:
                error = round( abs(opticalTRCData[currFrame][1][currMarker][0] - simulatedHybridTRCData[currFrame][1][currMarker][0]),  4)
                errorSum += error
                errorValues.append(error)
                currMarker += 1

        currFrame += 1

        grabFrameCounter += 1
        if grabFrameCounter == opticalSkipFactor:
            grabFrameCounter = 0

    
    # avgError = errorSum/(len(errorValues)*numMarkers)
    standardDeviation = np.std(errorValues)
    average = np.average(errorValues)
    
    return average, standardDeviation

if __name__ == '__main__':
    # Call freeze_support() to protect the main entry point on Windows
    freeze_support()

    # Sine Error Function Parameters
    amplitude = 89.2
    frequency = 0.9  # in Hz (cycles per second)
    verticalShift = 89.2 
    # Occlusion Parameters
    occlusionNumber = 25 # how many markers to occlude at any given time (0-49)
    occlusionDuration = 10 # how long an occlusion for a given marker lasts, in seconds.
    opticalSkipFactor = 4 # Inertial fps = 120, thus optical optical fps = 30
    # File Paths
    inFilePath = r'C:\Users\lando\OneDrive\Desktop\Research_Project\Code\Graphing_Code\trc_original.trc'
    outFilePath = r'C:\Users\lando\OneDrive\Desktop\Research_Project\Code\Graphing_Code\output.trc'

    inTRCData = TRCData()
    inTRCData.load(inFilePath)
    numFrames = inTRCData['NumFrames']    
    allMarkerNames = inTRCData['Markers']
    inertialFPS = inTRCData['DataRate']
    opticalFPS = inertialFPS/opticalSkipFactor
    markers = createMarkerObjectList(allMarkerNames)

    inertialQueue = Queue()
    opticalQueue = Queue()
    fusedQueue = Queue()

    feederFunc(inTRCData, inertialFPS, inertialQueue, opticalQueue, opticalSkipFactor, numFrames)
    fuser(inertialQueue, opticalQueue, fusedQueue, opticalFPS, occlusionDuration, occlusionNumber, markers, amplitude, frequency, verticalShift, numFrames)
    writeToOutfile( fusedQueue, inFilePath, outFilePath )
    
    avgError, standardDevation = produceOpticalComparisonStats( inTRCData, outFilePath, numFrames, len(allMarkerNames), opticalSkipFactor )
    
    print(avgError)
    print(standardDevation)










# old new occluder
            # oldGroupIndexes = oclGroupIndexes       # seed new random group, all new members (compared to previous random group)
            # oclGroupIndexes = []
            # for _ in range( 0, occlusionNumber ):
            #     random_num = random.randint(0, len(markers) - 1)
            #     alreadyChosen = random_num in oclGroupIndexes
            #     repeat = random_num in oldGroupIndexes
            #     invalidNum = alreadyChosen | repeat
            #     while invalidNum:
            #         random_num = random.randint(0, len(markers) - 1)
            #         alreadyChosen = random_num in oclGroupIndexes
            #         repeat = random_num in oldGroupIndexes
            #         invalidNum = alreadyChosen | repeat
            #     oclGroupIndexes.append(random_num)



# old drifter
# def drifter( inertialFrame: tuple, opticalFrame: tuple, markers: list, factorX: int, factorY: int, factorZ: int ):

#     count = 0
#     for marker in opticalFrame[1]:
#         if marker == 'N/A':

#             # find which group the current marker belongs to:
#             currentGroupIndex = -1
#             potentialIndex = 0
#             for group in groupsWithCounts:
                
#                 for markers in group[2]:
#                     if markersNamesFrameOrder[count] == markers:
#                         currentGroupIndex = potentialIndex
#                         break
                
#                 if currentGroupIndex > -1:
#                     break
#                 potentialIndex += 1

#             # add +1 to consecutiveInertialFrames of currentGroupIndex within groupsWithCounts.
#             groupsWithCounts[currentGroupIndex] = ( groupsWithCounts[currentGroupIndex][0], groupsWithCounts[currentGroupIndex][1] + 1, groupsWithCounts[currentGroupIndex][2] )

#             # go through opticalFrame again, adding drifted readings to members of currentGroupIndex
#             count2 = 0
#             for marker3 in opticalFrame[1]:
#                 if markersNamesFrameOrder[count2] in groupsWithCounts[currentGroupIndex][2]:
#                     opticalFrame[1][count2] = addDriftToReading( inertialFrame[1][count2], groupsWithCounts[currentGroupIndex][1], factorX, factorY, factorZ ) 
#                 count2 += 1
#         count += 1

#     return opticalFrame


 # old occluder
# def occluder( TRCframe: tuple, opticalFPS: int, occlusionSeconds: float, numGroupsToOcl: int, groupsWithCounts: list, markersNamesFrameOrder: list ):

#     framesToOcclude = int(opticalFPS * occlusionSeconds)
#     totalGroupCount = len(groupsWithCounts)
#     groupsBeingOccluded = False
#     framesLimitReached = False

#     # is there a group currently being occluded? Has the limit been reached?
#     for group in groupsWithCounts:
#         if group[0] > 0:
#             groupsBeingOccluded = True
#             if group[0] == framesToOcclude:
#                 framesLimitReached = True
#             break

#     # if limit reached, reset occlusion counts and flags
#     if framesLimitReached:

#         groupsBeingOccluded = False      # to signal creation of new group to occlude below
#         count1 = 0
#         for group in groupsWithCounts:
#             if group[0] > 0:
#                 groupsWithCounts[count1] = (0, group[1], group[2])
#             count1 += 1

#     #if not reached, remove reading and increment counter
#     elif groupsBeingOccluded == True:

# ################################### using 'group[0] > 0' HERE doesnt take into account that two different random groups
# ################################### might have share the same members.
# # FIXED I BELIEVE


#         count2 = 0
#         for group in groupsWithCounts:
#             if group[0] > 0:  ## HERE
#                 groupsWithCounts[count2] = (group[0] + 1, group[1], group[2])
#                 TRCframe = removeReading(TRCframe, group[2], markersNamesFrameOrder)
#             count2 = count2 + 1

#         return TRCframe

#     # if no groups being occluded, pick random group, remove readings, increment
#     if  (groupsBeingOccluded == False):

#         #pick group of random numbers
#         random_nums = []
#         for _ in range(int(numGroupsToOcl)):
#             random_num = random.randint(0, totalGroupCount - 1)
#             while random_num in random_nums:
#                 random_num = random.randint(0, totalGroupCount - 1)
#             random_nums.append(random_num)

#         # for random groups chosen, remove readings and increment counts
#         for number in random_nums:
#             groupsWithCounts[number] = (1, groupsWithCounts[number][1], groupsWithCounts[number][2])
#             TRCframe = removeReading(TRCframe, groupsWithCounts[number][2], markersNamesFrameOrder)

#         # reset the consecutive inertial frame count and the occluded optical frame count for groups not in the set of occluded groups
#         for num in range(0, totalGroupCount):
#             if num not in random_nums:
#                 groupsWithCounts[num] = (0, 0, groupsWithCounts[num][2])

#         return TRCframe




# def fuser(inertialQueue: Queue, opticalQueue: Queue, fps: int, oclSeconds: float, numGroupsToOcclude: int, 
#           groupsWithCounts: list, markersNamesFrameOrder: list, driftX: int, driftY: int, driftZ: int, frameCount: int, fusedQueue: Queue ):

#     bothQueueGrabCounter = 0
#     while inertialQueue.qsize() > 0 | opticalQueue.qsize() > 0:

#         if bothQueueGrabCounter == 0:   # get optical and inertial
            
#             inert = inertialQueue.get()
#             optic = opticalQueue.get()
#             occludedOptical = occluder( optic, fps, oclSeconds, numGroupsToOcclude, groupsWithCounts, markersNamesFrameOrder )
#             driftedFused = drifter( inert, occludedOptical, markersNamesFrameOrder, groupsWithCounts, driftX, driftY, driftZ ) #fill occluded markers with drifted inertial readings
#             fusedQueue.put(driftedFused)

# #for those that aren't occluded we must reset the consecutive inertial frame count.  Where should that be done?
            
#         else:   # just get inertial, create empty frame to pass to drifter for a complete filling of readings.
            
#             inert = inertialQueue.get()        
#             emptyFrame = copy.deepcopy(inert)
#             count = 0
#             for reading in emptyFrame[1]:
#                 emptyFrame[1][count] = 'N/A'
#                 count += 1
#             driftedFused = drifter( inert, emptyFrame, markersNamesFrameOrder, groupsWithCounts, driftX, driftY, driftZ )
#             fusedQueue.put(driftedFused)

    
#         bothQueueGrabCounter =  bothQueueGrabCounter + 1
#         if bothQueueGrabCounter == 4:
#             bothQueueGrabCounter = 0

#     for groups in groupsWithCounts:
#         print(groups[1])





#old main

# Number of markers to occlude
    # how long to occlude a marker for (thus we must make sure that a given marker is not occluded twice in a row)

    # resultant numbers we want:
    # Average accuracy of all markers
    # Standard Deviation of all markers
    # Accuracy of occluded markers. 
    # STD sort of shows this?
    # we can append different mocap sets together to get longer sessions.

    # percentOfGroupsToOcclude = 11/12      #denominator cant be greater than total group count   (opposite of how i thought)  Its actually num groups to not occlude
    # numGroupsToOcclude = (len(markers) // (1/(percentOfGroupsToOcclude)))  

    # inertialQueue = Queue()
    # opticalQueue = Queue()
    # fusedQueue = Queue()

    
   


# old groups
    # head = ['TopHead', 'LfFtHead', 'LtBkHead', 'RtFtHead', 'RtBkHead']
    # chest = ['LtCtChest', 'RtCtChest', 'LtChest', 'RtChest' ]
    # upperBack = ['Spine1', 'Spine2', 'Spine3', 'SpineOffsetHigh' ]
    # lowerBack = ['Root', 'SpineOffsetLow', 'LtBkHip', 'RtBkHip']
    # rightArm = ['RtShoulder', 'RtBicep', 'RtElbow','RtForeArm' ]
    # rightHand = ['RtWrist', 'RtPinky', 'RtThumb', 'RtMiddFing' ]
    # leftArm = ['LtShoulder', 'LtBicep', 'LtElbow','LtForeArm' ]
    # leftHand = ['LtWrist', 'LtPinky', 'LtThumb', 'LtMiddFing' ]
    # lowerRightLeg = [ 'RtAnkle', 'RtHeel', 'RtBall', 'RtToe']
    # upperRightLeg = ['RtCalf','RtKnee','RtThigh','RtFtHip']
    # lowerLeftLeg = ['LtAnkle', 'LtHeel', 'LtBall', 'LtToe']
    # upperLeftLeg = ['LtCalf', 'LtKnee','LtThigh','LtFtHip']
    # grouping = [head, chest, upperBack, lowerBack, rightArm, rightHand, leftArm, leftHand, lowerRightLeg, upperRightLeg, lowerLeftLeg, upperLeftLeg ]
