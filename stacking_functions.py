from functions import galaxia_puntos
import numpy as np
import random
from alive_progress import alive_bar
import numina.array

def get_cubelets(num_galaxies, redshifts, rest_freq, freq_ini, channel_to_freq, num_channels_cubelets, num_pixels_cubelets, coords_RA, coords_DEC, X_AR_ini, pixel_X_to_AR, Y_DEC_ini, pixel_Y_to_Dec, datacube, wcs, flux_units, is_PSF, show_verifications):
    """
    Function that extract cubelets around the galaxies of the data datacube. We extract the whole spectral range.

    • Input
    - num_galaxies [int]: Number of galaxies of the sample
    - num_channels_cubelets [array - int]: Number of channels in spectral axis extracted around each galaxy's emission line
    - num_pixels_cubelets [array - int]: Semirange of spaxels extracted around each galaxy
    - list_pixels_X [array - int]: Horizontal positions of the galaxies
    - list_pixels_Y [array - int]: Vertical positions of the galaxies
    - X_AR_ini [float]: Initial value of pixel X (deg)
    - pixel_X_to_AR [float]: Ratio pixel X (pix)/AR (deg)
    - Y_DEC_ini [float]: Initial value of pixel Y (deg)
    - pixel_Y_to_Dec [float]: Ratio pixel Y (pix)/Dec (deg)
    - datacube [array - float]: Datacube
    - wcs [WCS]: WCS of the file
    - flux_units [string]: Units of the flux
    - show_verifications [bool]: If 'True', plot the spatial position of each galaxy in the datacube

    • Output
    - cubelets [array - float]: Array of cubelets of each galaxy
    """

    #* First we convert degrees into pixels coordinates
    if(is_PSF == True):
        central_spaxel_Y, central_spaxel_X = datacube.shape[1]/2, datacube.shape[2]/2
        list_pixels_X, list_pixels_Y = np.repeat(central_spaxel_X, num_galaxies), np.repeat(central_spaxel_Y, num_galaxies)
    else:
        list_pixels_X = np.zeros(num_galaxies, int) #* Horizontal pixel position of the galaxies
        list_pixels_Y = np.zeros(num_galaxies, int) #* Vertical pixel position of the galaxies
        for i in range(num_galaxies):
            list_pixels_X[i] = int((coords_RA[i]-X_AR_ini)/pixel_X_to_AR)
            list_pixels_Y[i] = int((coords_DEC[i]-Y_DEC_ini)/pixel_Y_to_Dec)

    if show_verifications:
        galaxia_puntos(datacube, wcs, list_pixels_X, list_pixels_Y, 1, 1200, 1, 1200, X_AR_ini, pixel_X_to_AR, Y_DEC_ini, pixel_Y_to_Dec, flux_units, 12, 12, 15, 0.00005, None, None)

    #* Now we extract the sub-cubes (cubelets) of num_pixels_cubelets*num_pixels_cubelets px^2 around each galaxy, so the galaxies are spatially centered in their cubelet
    #!!! Have to do something if the galaxy is on the edge of the area of the cube: the spaxels that are out of the boundaries should have null spectra (?)
    cubelets = []#np.zeros((num_galaxies, num_channels_cubelets, 2*num_pixels_cubelets+1, 2*num_pixels_cubelets+1)) #*Number of galaxies, spectral length, Y length, X length
    for index, z in enumerate(redshifts):
        emission_position = rest_freq/(1+z) #* Frequency of the position of the emission line (spectral observational position - not at rest)
        channel_emission = int((emission_position - freq_ini)/channel_to_freq) #* Channel of the emission line (spectral observational position - not at rest)
        num_pixels = num_pixels_cubelets[index]
        num_channels = num_channels_cubelets[index]
        max_range = datacube.shape[0]
        z_min = int(channel_emission - num_channels)
        z_max = int(channel_emission + num_channels + 1)
        y_min = int(list_pixels_Y[index] - num_pixels)
        y_max = int(list_pixels_Y[index] + num_pixels + 1)
        x_min = int(list_pixels_X[index] - num_pixels)
        x_max = int(list_pixels_X[index] + num_pixels + 1)
        try:
            if(z_min >= 0):
                if(z_max < max_range):
                    cubelets.append(datacube[z_min:z_max, y_min:y_max, x_min:x_max])
                else:
                    cubelets.append(np.concatenate((datacube[z_min:, y_min:y_max, x_min:x_max], datacube[:z_max-max_range, y_min:y_max, x_min:x_max])))
            else:
                cubelets.append(np.concatenate((datacube[z_min:, y_min:y_max, x_min:x_max], datacube[:z_max, y_min:y_max, x_min:x_max])))
                
        except:
            print("\nEmpty cubelet :(")
            #cubelets.append(np.zeros(cubelets[i].shape))
            print(f"\nWe could not extract the cubelet centered on (x, y) = ({list_pixels_X[i]}, {list_pixels_Y[i]}).\n")

        if(cubelets[index].shape[0] == 0):
            print("\nMala onda\n")
            exit()

        if(cubelets[index].shape[0] == 457):
            print("alors", channel_emission, num_channels)
            exit()
        
          
    return cubelets    

def shift_and_wrap(num_galaxies, redshifts, rest_freq, freq_ini, channel_to_freq, expected_emission_channel, num_channels_original, num_pixels_cubelets, cubelets):
    """
    Function that shifts the spectral axis of cubelets around the frequency of interest (HI - 1420 MHz) and then wrap the part of the spectrum that is out of boundaries.

    • Input
    - num_galaxies [int]: Number of galaxies of the sample
    - redshifts [array - float]: Redshifts of all the galaxies
    - rest_freq [float]: Frequency around which spectra are shifted and wrapped
    - freq_ini [float]: Initial frequency (Hz)
    - channel_to_freq [float]: Ratio between channel and frequency
    - expected_emission_channel [int]: Channel where the emission line will lie at the end of the shifting/wrapping process
    - num_channels_cubelets [array - int]: Number of channels of each cubelets
    - num_pixels_cubelets [array - int]: Semirange of spaxels extracted around each galaxy
    - cubelets [array - float]: Array of cubelets of each galaxy

    • Output
    - shifted_wrapped_cubelets [array - float]: Array of cubelets shifted and wrapped of each galaxy
    """

    #* We start by finding for each spectrum the position of their emission line. We want to place each spectrum centered on its emission line. In order to do that we have to calculate on which channel this line is and make it the centered channel of the stacked spectrum
    shifted_wrapped_cubelets = []
    for index, redshift in enumerate(redshifts):
        emission_position = rest_freq/(1+redshift) #* Frequency of the position of the emission line (spectral observational position - not at rest)
        channel_emission = int((emission_position - freq_ini)/channel_to_freq) #* Channel of the emission line (spectral observational position - not at rest)
        shift_in_channels = int(expected_emission_channel - channel_emission) #* Number of channels that we have to shift the spectrum in order to center it (-: left, +: right)
        num_pixels = num_pixels_cubelets[index]
        num_channels = num_channels_original
        cubelet = cubelets[index]
        shifted_wrapped_cubelet = np.zeros((num_channels_original, 2*num_pixels+1, 2*num_pixels+1))
        for pixel_Y in range(2*num_pixels+1):
            for pixel_X in range(2*num_pixels+1):
                if(shift_in_channels < 0): #* Shift to the left + wrap
                    shifted_wrapped_cubelet[:, pixel_Y, pixel_X] = np.concatenate((cubelet[abs(shift_in_channels):, pixel_Y, pixel_X], cubelet[:abs(shift_in_channels), pixel_Y, pixel_X]))


                elif(shift_in_channels > 0): #* Shift to the right + wrap
                    shifted_wrapped_cubelet[:, pixel_Y, pixel_X] = np.concatenate((cubelet[(num_channels-shift_in_channels):, pixel_Y, pixel_X], cubelet[:(num_channels-shift_in_channels), pixel_Y, pixel_X]))

                else: #* No shift nor wrap
                    shifted_wrapped_cubelet[:, pixel_Y, pixel_X] = cubelet[:, pixel_Y, pixel_X]

        shifted_wrapped_cubelets.append(shifted_wrapped_cubelet)

    return shifted_wrapped_cubelets

def stacking_process(type_of_datacube, num_galaxies, num_channels_cubelets, num_pixels_cubelets, central_width, pre_stacking_cubelets, weights_option, lum_distance):
    """ 
    Function that stack the cubelets.

    • Input
    - num_galaxies [int]: Number of galaxies of the sample
    - num_channels_cubelets [int]: Number of channels in spectral axis
    - num_pixels_cubelets [int]: Semirange of spaxels extracted around each galaxy
    - central_width [int]: Number of channels where we consider the central (HI) lies; used for calculating sigma
    - pre_stacking_cubelets [array - float]: Array of cubelets shifted and wrapped of each galaxy
    - weights_option [str]: Option used to calculate the weights
    - lum_distance [float]: luminosity distance of the galaxies, used to calculate Delhaize's weights 
    !!! Make the lum_distance optional

    • Output
    - stacked_cube [array - float]: Stacked datacube 
    """

    stacked_cube = np.zeros((num_channels_cubelets, 2*num_pixels_cubelets+1, 2*num_pixels_cubelets+1))
    
    with alive_bar((2*num_pixels_cubelets+1)*(2*num_pixels_cubelets+1)*num_galaxies, bar='circles', title=f'{type_of_datacube} stacking in progress') as bar:
        for pixel_Y in range(2*num_pixels_cubelets+1):
            for pixel_X in range(2*num_pixels_cubelets+1):
                rescale = 0
                for i in range(num_galaxies):
                    continuum_spectrum = np.concatenate((pre_stacking_cubelets[i, :int(num_channels_cubelets/2)-central_width, pixel_Y, pixel_X], pre_stacking_cubelets[i, int(num_channels_cubelets/2)+central_width:, pixel_Y, pixel_X])) #* We use the continuum in order to calculate sigma and use it in the weights
                    sigma = np.std(continuum_spectrum)

                    weight = 1
                    if(weights_option=='fabello'):
                        weight = 1/sigma**2
                    elif(weights_option=='lah'):
                        weight = 1/sigma
                    elif(weights_option=='delhaize'):
                        weight = 1/(sigma*lum_distance**2)**2
                    elif(weights_option=='None'):
                        weight = 1

                    rescale += weight
                    stacked_cube[:, pixel_Y, pixel_X] += pre_stacking_cubelets[i, :, pixel_Y, pixel_X]*weight
                    bar()
                #* We divide the integrated flux by the number of galaxies 
                stacked_cube[:, pixel_Y, pixel_X] /= rescale
    
    """for i in range(num_galaxies):
        for y in range(stacked_cube.shape[1]):
            for x in range(stacked_cube.shape[2]):
                if max(stacked_cube[:, y, x]) > 10:
                    print(x, y, np.argmax(stacked_cube[:, y, x]), max(stacked_cube[:, y, x]))
    exit()"""
    
    return stacked_cube

def datacube_stack(type_of_datacube, num_galaxies, num_channels_cubelets, num_pixels_cubelets, expected_emission_channel, coords_RA, coords_DEC, X_AR_ini, pixel_X_to_AR, Y_DEC_ini, pixel_Y_to_Dec, datacube, wcs, flux_units, redshifts, rest_freq, freq_ini, channel_to_freq, central_width, num_pixels_cubelets_final, num_channels_cubelets_final, expected_emission_channel_final, weights_option, lum_distance, show_verifications):
    """
    Metafunction that extract the cubelets, shift and wrap them and stack them.

    • Input
    - num_galaxies [int]: Number of galaxies of the sample
    - num_channels_cubelets [array - int]: Number of channels in spectral axis extracted around each galaxy's emission line
    - num_pixels_cubelets [array - int]: Semirange of spaxels extracted around each galaxy
    - coords_RA [array - float]: List of the horizontal coordinates of each galaxy (in deg)
    - coords_DEC [array - float]: List of the vertical coordinates of each galaxy (in deg)
    - X_AR_ini [float]: Initial value of pixel X (deg)
    - pixel_X_to_AR [float]: Ratio pixel X (pix)/AR (deg)
    - Y_DEC_ini [float]: Initial value of pixel Y (deg)
    - pixel_Y_to_Dec [float]: Ratio pixel Y (pix)/Dec (deg)
    - datacube [array - float]: Array of the data datacube
    - wcs [WCS]: WCS of the file
    - flux_units [string]: Units of the flux
    - redshifts [array - float]: Redshifts of all the galaxies
    - rest_freq [float]: Frequency around which spectra are shifted and wrapped
    - freq_ini [float]: Initial frequency (Hz)
    - channel_to_freq [float]: Ratio between channel and frequency
    - central_width [int]: Number of channels where we consider the central (HI) lies; used for calculating sigma
    - num_pixels_cubelets_final [int]: Final semirange of spaxels extracted around each galaxy used in the regrid process
    - weights_option [str]: Option used to calculate the weights
    - lum_distance [float]: luminosity distance of the galaxies, used to calculate Delhaize's weights 
    !!! Make the lum_distance optional
    - show_verifications [bool]: If 'True', plot the spectrum of one of the shifted and wrapped subelets

    • Output
    - stacked_cube [array - float]: Stacked datacube 
    """

    #* We use the spatial and spectral coordinates to extract cubelets of the galaxies

    if(type_of_datacube == 'Noise'):
        redshifts = random.sample(list(redshifts), len(redshifts))

    if(type_of_datacube == 'PSF'):
        cubelets = get_cubelets(num_galaxies, redshifts, rest_freq, freq_ini, channel_to_freq, num_channels_cubelets, num_pixels_cubelets, None, None, X_AR_ini, pixel_X_to_AR, Y_DEC_ini, pixel_Y_to_Dec, datacube, wcs, flux_units, True, show_verifications)
    else:
        cubelets = get_cubelets(num_galaxies, redshifts, rest_freq, freq_ini, channel_to_freq, num_channels_cubelets, num_pixels_cubelets, coords_RA, coords_DEC, X_AR_ini, pixel_X_to_AR, Y_DEC_ini, pixel_Y_to_Dec, datacube, wcs, flux_units, False, show_verifications)

    #* Now we shift each spectrum in each subcube to place it in rest frame with its HI emission at central channel
    #!!! Possible problem: if some cubelets have same spaxels (don't know if it's an issue)

    #shifted_wrapped_cubelets = shift_and_wrap(num_galaxies, redshifts, rest_freq, freq_ini, channel_to_freq, expected_emission_channel, datacube.shape[0], num_pixels_cubelets, cubelets)

    """sub_cubelets = []

    for index, redshift in enumerate(redshifts):
        emission_position = rest_freq/(1+redshift) #* Frequency of the position of the emission line (spectral observational position - not at rest)
        channel_emission = int((emission_position - freq_ini)/channel_to_freq) #* Channel of the emission line (spectral observational position - not at rest)
        cubelet = shifted_wrapped_cubelets[index]
        sub_cubelets.append(cubelet[expected_emission_channel-num_channels_cubelets[index]:expected_emission_channel+num_channels_cubelets[index]+1, :, :])"""

    """
    if(show_verifications):
        index, pixel_Y, pixel_X = 32, 6, 9
        fig, ax = plt.subplots(figsize=(19.2, 10.8))

        ax.plot(np.linspace(1, num_channels_cubelets, num_channels_cubelets), shifted_wrapped_cubelets[index, :, pixel_Y, pixel_X]+np.ones(num_channels_cubelets)*0.0005, label="shifted part")
        ax.plot(np.linspace(1, num_channels_cubelets, num_channels_cubelets), cubelets[index, :, pixel_Y, pixel_X], label="original")
        ax.vlines(emission_position, min(cubelets[index, :, pixel_Y, pixel_X]), max(cubelets[index, :, pixel_Y, pixel_X]), linestyles='dashdot', color='red', label='HI position',  alpha=1, zorder=0)
        ax.vlines(emission_position+my_shift, min(shifted_wrapped_cubelets[index, :, pixel_Y, pixel_X])+0.0005, max(shifted_wrapped_cubelets[index, :, pixel_Y, pixel_X])+0.0005, linestyles='dashdot', color='red', alpha=1, zorder=0)
        if(my_shift>0):
            ax.fill_between(np.linspace(0, abs(my_shift), 1000), min(cubelets[32, :, 6, 9])+0.0005, max(cubelets[32, :, 6, 9])+0.0005, color='green', alpha=0.25, label="Shift=%i" %my_shift)
            ax.fill_between(np.linspace(num_channels_cubelets - abs(my_shift), num_channels_cubelets, 1000), min(shifted_wrapped_cubelets[32, :, 6, 9]), max(shifted_wrapped_cubelets[32, :, 6, 9]), color='green', alpha=0.25)
        else:
            ax.fill_between(np.linspace(0, abs(my_shift), 1000), min(cubelets[index, :, pixel_Y, pixel_X]), max(cubelets[index, :, pixel_Y, pixel_X]), color='green', alpha=0.25, label="Shift=%i" %my_shift)
            ax.fill_between(np.linspace(num_channels_cubelets - abs(my_shift), num_channels_cubelets, 1000), min(shifted_wrapped_cubelets[index, :, pixel_Y, pixel_X])+0.0005, max(shifted_wrapped_cubelets[index, :, pixel_Y, pixel_X])+0.0005, color='green', alpha=0.25)
        ax.legend(loc='best')

        #?Figure's labels
        ax.set_xlabel("Channels", labelpad=1)
        ax.set_ylabel("Relative flux", labelpad=0)
        ax.set_title('Shift and wrapping processes example')
        ax.tick_params(axis='y', labelsize=0, length=0)

        #?Save the figure
        plt.tight_layout()
        path = '/Verification_process/'
        if not os.path.isdir(path):
            os.makedirs(path)

        plt.savefig("%sshift_wrap_process.pdf" %path) #?Guardamos la imagen
    """

    #* Now we have to re-grid the cubelets so they have the same dimensions before the stacking
    #!!! Should interpolate?!?
    pre_stacking_cubelets = np.zeros((num_galaxies, num_channels_cubelets_final, 2*num_pixels_cubelets_final+1, 2*num_pixels_cubelets_final+1))
    for i in range(num_galaxies):
        pre_stacking_cubelets[i] = numina.array.rebin(cubelets[i], (num_channels_cubelets_final, 2*num_pixels_cubelets_final+1, 2*num_pixels_cubelets_final+1))

    """import matplotlib.pyplot as plt

    f, axarr = plt.subplots(1, 2, figsize=(12.8, 7.2))

    # use the created array to output your multiple images. In this case I have stacked 4 images vertically
    axarr[0].imshow(shifted_wrapped_cubelets[3][121, :, :])
    axarr[1].imshow(pre_stacking_cubelets[3, 121, :, :])

    plt.show()"""
    
    #* The number of channels for the new spectrum will be 242*2, which is the maximum number of channels that can be necessary for co-adding the spectra (supposing emission line in channel 1 and in channel 242 for two different spectra).

    stacked_cube = stacking_process(type_of_datacube, num_galaxies, num_channels_cubelets_final, num_pixels_cubelets_final, central_width, pre_stacking_cubelets, weights_option, lum_distance)

    return stacked_cube
