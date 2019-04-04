# import necessary libraries
from nadir import *
import os,sys
from PIL import Image
import math
import numpy as np
import scipy.misc
import time
import matplotlib.pyplot as plt

def main(rgramFile, surfType = 'nadir'):
    '''
    script extracts power of surface return from radargram
    surface return can be defined as either first return (fret), nadir return, or 
    the max power return - return from which most radar energy penetrates surface (max)
    this will run through all .img radargrams in directory.
    designed to run on directory structured like PDS.

    author: Brandon S. Tober
    created: 30January2018
    updated: 04APR19
    '''
    t0 = time.time()                                                                                                        # start time
    print('--------------------------------')
    print('Extracting surface power [' + surfType + '] for observation: ' + fileName)
    navFile = np.genfromtxt(in_path + 'processed/data/geom/' + fileName + '_geom.csv', delimiter = ',', dtype = None)       # open geom nav file for rgram to append surface echo power to each trace                                                 
    amp = np.load(rgramFile)
    pow = np.power(amp,2)                                                                                                   # convert amplitude radargram to power (squared amp)                                          
    (r,c) = amp.shape   

    if surfType == 'nadir':

        nadbin = np.zeros(c)                                                                                                # empty array to hold pixel location for each trace of nadir location
        binsize = .0375e-6
        speedlight = 299792458
        shift = navFile[:,12]                                                                                               # receive window opening time shift from EDR aux data


        dem_path = mars_path + '/code/modl/MRO/simc/test/temp/dem/megt_128_merge.tif'                                       # Grab megt and mega,  mola dem and aeroid 
        aer_path = mars_path + '/code/modl/MRO/simc/test/temp/dem/mega_16.tif'

        navdat = GetNav_geom(navPath)
 
        topo = Dem(dem_path)

        nad_loc = navdat.toground(topo,navdat.csys)

        aer = Dem(aer_path)

        aer_nadir = navdat.toground(aer)

        for i in range(len(navdat)):
            if(aer_nadir[i].z == aer.nd):
                aer_nadir[i].z = aer_nadir[i-1].z
            navdat[i].z = navdat[i].z - aer_nadir[i].z                                                                      # MRO elevation above aeroid: subtract out spheroid and aeroid
            if np.abs(nad_loc[i].z) > 1e10:                                                                                 # account for no data values from mola dem - assign previous value if n.d.
                nad_loc[i].z = nad_loc[i-1].z
            nadbin[i] = int(((navdat[i].z-nad_loc[i].z)*2/speedlight)/binsize) - shift[i]                                   # take MRO height above aeroid, subtract mola elevation, account for SHARAD receive window opening time shift and convert to pixels 
            nadbin[i] = nadbin[i] % 3600                                                                                    # take modulo in case pixel is location of nadir is greater then max rgram dimensions

        # plt.subplot(2,2,1)
        # plt.title('PRI')
        # plt.plot(navFile[:,10])
        # plt.subplot(2,2,2)
        # plt.title('RECEIVE_WINDOW_OPEINING_TIME')
        # plt.plot(navFile[:,11])
        # plt.subplot(2,2,3)
        # plt.title('RECEIVE_WINDOW_POSITION_SHIFT')
        # plt.plot(shift)
        # plt.subplot(2,2,4)
        # plt.title('nadir_bin')
        # plt.plot(nadbin)
        # plt.show()

        surf = nadbin

    elif surfType == 'fret':
        '''       
        criteria for surface echo - indicator is Pt * dPt-1/dt, 
        where P is the signal energy applied on each grame sample (t).
        Indicator weights energy of a sample by the derivative preceding it
        '''
        C = np.empty((r,c))	                                                                                                # create empty criteria array to localize surface echo for each trace

        gradient = np.gradient(pow, axis = 0)                                                                               # find gradient of each trace in RGRAM

        C[100:r,:] = pow[100:r,:]*gradient[99:r-1,:]                                                                        # vectorized criteria calculation
        
        C_max_ind = np.argmax(C, axis = 0)	                                                                                # find indices of max critera seletor for each column

        surf = C_max_ind
    
    elif surfType == 'max':
        print('Code not set up to handle max power return as of yet - BT')
        sys.exit()


    # record surface power in text file and geomdata file
    surf = surf.astype(int)
    surfPow = np.empty((c,1))
    surfAmp = np.reshape(amp[surf, np.arange(c)], (c,1))                                                                    # record power in dB
    surfPow = 20 * (np.log10(surfAmp))


    if navFile.shape[1] == 13:                                                                                              # append surf pow values to geom.tab file. this should be the 13th column
        navFile = np.append(navFile, surfAmp, 1)

    else:                                                                                                                   # if surfPow with specified surf has already been run and it is being re-run, overwrite 6th column with new pow values
        navFile[:,14] = surfAmp[:,0]

    np.savetxt(out_path + fileName + '_geom_' + surfType + '.csv', navFile, delimiter = ',', newline = '\n', fmt= '%s')
    np.savetxt(out_path + fileName + '_' + surfType + '_pow.txt', surfAmp, delimiter=',', \
        newline = '\n', comments = '', header = 'PDB', fmt='%.8f')


    maxPow = np.argmax(pow, axis = 0)                                                                                       # find max power in each trace
    # stack data to reduce for visualization
    stackFac = 16
    stackCols = int(np.ceil(amp.shape[1]/stackFac))
    ampStack = np.zeros((3600, stackCols))   
    surfStack = np.zeros(stackCols)
    maxStack = np.zeros(stackCols)
    for _i in range(stackCols - 1):
        ampStack[:,_i] = np.mean(amp[:,stackFac*_i:stackFac*(_i+1)], axis = 1)
        surfStack[_i] = np.mean(surf[stackFac*_i:stackFac*(_i+1)])
        maxStack[_i] = np.mean(maxPow[stackFac*_i:stackFac*(_i+1)])
    # account for traces left if number of traces is not divisible by stackFac
    ampStack[:,-1] = np.mean(amp[:,stackFac*(_i+1):-1], axis = 1)
    surfStack[-1] = np.mean(surf[stackFac*(_i+1):-1])
    maxStack[-1] = np.mean(maxPow[stackFac*(_i+1):-1])
    
   
    surfStack = surfStack.astype(int)
    maxStack = maxStack.astype(int)


    # rescale rgram for visualization to plot surfPick
    powStack = np.power(ampStack,2)                                                                                         # convert amplitude radargram to power (squared amp)
    noise_floor = np.mean(powStack[:50,:])                                                                                  # define a noise floor from average power of flattened first 50 rows
    dB = 10 * np.log10(powStack / noise_floor)                                                                              # scale image array by max pixel to create jpg output with fret index
    maxdB = np.amax(dB, axis = 0)
    ampScale = dB / maxdB * 255
    ampScale[np.where(ampScale < 0)] = 0.
    ampScale[np.where(ampScale > 255)] = 255.
    # ampScale = np.abs(ampScale - 255)                                                                                       # reverse color scheme black on white

    imarray = np.zeros((r,stackCols,3), 'uint8')	                                                                        # create empty surf index and power arrays
    imarray[:,:,0] = imarray[:,:,1] = imarray[:,:,2] = ampScale[:,:]                                                        # create surf index image - show scaled radargram as base

    imarray[maxStack, np.arange(stackCols),0:2] = 0                                                                         # indicate max power along track as red
    imarray[maxStack, np.arange(stackCols),0] = 255  

    imarray[surfStack, np.arange(stackCols),0] = imarray[surfStack, np.arange(stackCols),1] = 255                           # make index given by fret algorithm yellow
    imarray[surfStack, np.arange(stackCols),2] = 0

    try:
        im = Image.fromarray(imarray, 'RGB')                                                             
        scipy.misc.imsave(out_path + fileName + '_' + surfType + '.png', im)
    except Exception as err:
        print(err)

    t1 = time.time()                                                                                                        # end time
    print('Total Runtime: ' + str(round((t1 - t0),4)) + ' seconds')
    print('--------------------------------')
    return

if __name__ == '__main__':
    
    # get correct data paths if depending on current OS
    mars_path = '/MARS'
    in_path = mars_path + '/orig/supl/SHARAD/EDR/hebrus_valles_sn/'
    out_path = mars_path + '/targ/xtra/SHARAD/surfPow/hebrus_valles_sn/'
    if os.getcwd().split('/')[1] == 'media':
        mars_path = '/media/anomalocaris/Swaps' + mars_path
        in_path = '/media/anomalocaris/Swaps' + in_path
        out_path = '/media/anomalocaris/Swaps' + out_path
    elif os.getcwd().split('/')[1] == 'mnt':
        mars_path = '/mnt/d' + mars_path
        in_path = '/mnt/d' + in_path
        out_path = '/mnt/d' + out_path
    elif os.getcwd().split('/')[1] == 'disk':
        mars_path = '/disk/qnap-2' + mars_path
        in_path = '/disk/qnap-2' + in_path
        out_path = '/disk/qnap-2' + out_path
    else:
        print('Data path not found')
        sys.exit()
   
    rgramFile = sys.argv[1]                                                                                                 # input radargram - range compressed - amplitude output
    fileName = rgramFile.split('_')[0] + '_' + rgramFile.split('_')[1]                                                      # base fileName
    rgramName = fileName.split('_')[0] + fileName.split('_')[1]                                                             # SHARAD rgram obs. #
    navPath = in_path + 'processed/data/geom/' + fileName + '_geom.csv'                                                     # path to nav file for obs.  
    rgramFile = in_path + 'processed/data/rgram/amp/' + rgramFile                                                           # attach input data path to beginning of rgram file name
    surfType = 'nadir'                                                                                                      # define the desired surface pick = [fret,narid,max]
  
    # check if surfPow has already been determined for desired obs. - if it hasn't run obs.
    if (not os.path.isfile(out_path + fileName \
         + '_geom_' + surfType + 'Pow.csv')):
        main(rgramFile, surfType = surfType)
    else:
        print('\nSurface power extraction [' + surfType + '] of observation' + rgramName \
            + ' already completed! Moving to next line!')

        
