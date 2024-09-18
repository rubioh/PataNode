import torch
import torch.nn as nn
from time import time
from scipy import signal
import numpy as np
from scipy.signal import get_window
from scipy.fftpack import fft
from nnAudio.librosa_functions import *
from torch.nn.functional import conv1d


def nextpow2(A):
    return int(np.ceil(np.log2(A)))


def downsampling_by_n(x, filterKernel, n):
    """A helper function that downsamples the audio by a arbitary factor n.
    It is used in CQT2010 and CQT2010v2.

    Parameters
    ----------
    x : torch.Tensor
        The input waveform in ``torch.Tensor`` type with shape ``(batch, 1, len_audio)``

    filterKernel : str
        Filter kernel in ``torch.Tensor`` type with shape ``(1, 1, len_kernel)``

    n : int
        The downsampling factor

    Returns
    -------
    torch.Tensor
        The downsampled waveform

    Examples
    --------
    >>> x_down = downsampling_by_n(x, filterKernel)
    """

    padding = int((filterKernel.shape[-1] - 1) // 2)
    x = conv1d(x, filterKernel, stride=(n,), padding=(padding,))
    return x


def downsampling_by_2(x, filterKernel):
    """A helper function that downsamples the audio by half. It is used in CQT2010 and CQT2010v2

    Parameters
    ----------
    x : torch.Tensor
        The input waveform in ``torch.Tensor`` type with shape ``(batch, 1, len_audio)``

    filterKernel : str
        Filter kernel in ``torch.Tensor`` type with shape ``(1, 1, len_kernel)``

    Returns
    -------
    torch.Tensor
        The downsampled waveform

    Examples
    --------
    >>> x_down = downsampling_by_2(x, filterKernel)
    """

    return downsampling_by_n(x, filterKernel, 2)


def complex_mul(cqt_filter, stft):
    """Since PyTorch does not support complex numbers and its operation.
    We need to write our own complex multiplication function. This one is specially
    designed for CQT usage.

    Parameters
    ----------
    cqt_filter : tuple of torch.Tensor
        The tuple is in the format of ``(real_torch_tensor, imag_torch_tensor)``

    Returns
    -------
    tuple of torch.Tensor
        The output is in the format of ``(real_torch_tensor, imag_torch_tensor)``
    """

    cqt_filter_real = cqt_filter[0]
    cqt_filter_imag = cqt_filter[1]
    fourier_real = stft[0]
    fourier_imag = stft[1]

    CQT_real = torch.matmul(cqt_filter_real, fourier_real) - torch.matmul(
        cqt_filter_imag, fourier_imag
    )
    CQT_imag = torch.matmul(cqt_filter_real, fourier_imag) + torch.matmul(
        cqt_filter_imag, fourier_real
    )

    return CQT_real, CQT_imag


def get_cqt_complex2(
    x, cqt_kernels_real, cqt_kernels_imag, hop_length, padding, wcos=None, wsin=None
):
    """Multiplying the STFT result with the cqt_kernel, check out the 1992 CQT paper [1]
    for how to multiple the STFT result with the CQT kernel
    [2] Brown, Judith C.C. and Miller Puckette. “An efficient algorithm for the calculation of
    a constant Q transform.” (1992)."""

    # STFT, converting the audio input from time domain to frequency domain
    try:
        x = padding(
            x
        )  # When center == True, we need padding at the beginning and ending
    except:
        warnings.warn(
            f"\ninput size = {x.shape}\tkernel size = {cqt_kernels_real.shape[-1]}\n"
            "padding with reflection mode might not be the best choice, try using constant padding",
            UserWarning,
        )
        x = torch.nn.functional.pad(
            x, (cqt_kernels_real.shape[-1] // 2, cqt_kernels_real.shape[-1] // 2)
        )

    if wcos == None or wsin == None:
        CQT_real = conv1d(x, cqt_kernels_real, stride=hop_length)
        CQT_imag = -conv1d(x, cqt_kernels_imag, stride=hop_length)

    else:
        fourier_real = conv1d(x, wcos, stride=hop_length)
        fourier_imag = conv1d(x, wsin, stride=hop_length)
        # Multiplying input with the CQT kernel in freq domain
        CQT_real, CQT_imag = complex_mul(
            (cqt_kernels_real, cqt_kernels_imag), (fourier_real, fourier_imag)
        )

    return torch.stack((CQT_real, CQT_imag), -1)


def broadcast_dim(x):
    """
    Auto broadcast input so that it can fits into a Conv1d
    """

    if x.dim() == 2:
        x = x[:, None, :]
    elif x.dim() == 1:
        # If nn.DataParallel is used, this broadcast doesn't work
        x = x[None, None, :]
    elif x.dim() == 3:
        pass
    else:
        raise ValueError(
            "Only support input with shape = (batch, len) or shape = (len)"
        )
    return x


def create_lowpass_filter(band_center=0.5, kernelLength=256, transitionBandwidth=0.03):
    """
    Calculate the highest frequency we need to preserve and the lowest frequency we allow
    to pass through.
    Note that frequency is on a scale from 0 to 1 where 0 is 0 and 1 is Nyquist frequency of
    the signal BEFORE downsampling.
    """

    # transitionBandwidth = 0.03
    passbandMax = band_center / (1 + transitionBandwidth)
    stopbandMin = band_center * (1 + transitionBandwidth)

    # Unlike the filter tool we used online yesterday, this tool does
    # not allow us to specify how closely the filter matches our
    # specifications. Instead, we specify the length of the kernel.
    # The longer the kernel is, the more precisely it will match.
    # kernelLength = 256

    # We specify a list of key frequencies for which we will require
    # that the filter match a specific output gain.
    # From [0.0 to passbandMax] is the frequency range we want to keep
    # untouched and [stopbandMin, 1.0] is the range we want to remove
    keyFrequencies = [0.0, passbandMax, stopbandMin, 1.0]

    # We specify a list of output gains to correspond to the key
    # frequencies listed above.
    # The first two gains are 1.0 because they correspond to the first
    # two key frequencies. the second two are 0.0 because they
    # correspond to the stopband frequencies
    gainAtKeyFrequencies = [1.0, 1.0, 0.0, 0.0]

    # This command produces the filter kernel coefficients
    filterKernel = signal.firwin2(kernelLength, keyFrequencies, gainAtKeyFrequencies)

    return filterKernel.astype(np.float32)


def get_early_downsample_params(sr, hop_length, fmax_t, Q, n_octaves, verbose):
    """Used in CQT2010 and CQT2010v2"""

    window_bandwidth = 1.5  # for hann window
    filter_cutoff = fmax_t * (1 + 0.5 * window_bandwidth / Q)
    sr, hop_length, downsample_factor = early_downsample(
        sr, hop_length, n_octaves, sr // 2, filter_cutoff
    )
    if downsample_factor != 1:
        if verbose == True:
            print("Can do early downsample, factor = ", downsample_factor)
        earlydownsample = True
        # print("new sr = ", sr)
        # print("new hop_length = ", hop_length)
        early_downsample_filter = create_lowpass_filter(
            band_center=1 / downsample_factor,
            kernelLength=256,
            transitionBandwidth=0.03,
        )
        early_downsample_filter = torch.tensor(early_downsample_filter)[None, None, :]

    else:
        if verbose == True:
            print(
                "No early downsampling is required, downsample_factor = ",
                downsample_factor,
            )
        early_downsample_filter = None
        earlydownsample = False

    return sr, hop_length, downsample_factor, early_downsample_filter, earlydownsample


def early_downsample(sr, hop_length, n_octaves, nyquist, filter_cutoff):
    """Return new sampling rate and hop length after early dowansampling"""
    downsample_count = early_downsample_count(
        nyquist, filter_cutoff, hop_length, n_octaves
    )
    # print("downsample_count = ", downsample_count)
    downsample_factor = 2 ** (downsample_count)

    hop_length //= downsample_factor  # Getting new hop_length
    new_sr = sr / float(downsample_factor)  # Getting new sampling rate
    sr = new_sr

    return sr, hop_length, downsample_factor


def early_downsample_count(nyquist, filter_cutoff, hop_length, n_octaves):
    """Compute the number of early downsampling operations"""

    downsample_count1 = max(
        0, int(np.ceil(np.log2(0.85 * nyquist / filter_cutoff)) - 1) - 1
    )
    # print("downsample_count1 = ", downsample_count1)
    num_twos = nextpow2(hop_length)
    downsample_count2 = max(0, num_twos - n_octaves + 1)
    # print("downsample_count2 = ",downsample_count2)

    return min(downsample_count1, downsample_count2)


def create_cqt_kernels(
    Q,
    fs,
    fmin,
    n_bins=84,
    bins_per_octave=12,
    norm=1,
    window="hann",
    fmax=None,
    topbin_check=True,
    gamma=0,
    pad_fft=True,
):
    """
    Automatically create CQT kernels in time domain
    """

    fftLen = 2 ** nextpow2(np.ceil(Q * fs / fmin))
    # minWin = 2**nextpow2(np.ceil(Q * fs / fmax))

    if (fmax != None) and (n_bins == None):
        n_bins = np.ceil(
            bins_per_octave * np.log2(fmax / fmin)
        )  # Calculate the number of bins
        freqs = fmin * 2.0 ** (np.r_[0:n_bins] / np.double(bins_per_octave))

    elif (fmax == None) and (n_bins != None):
        freqs = fmin * 2.0 ** (np.r_[0:n_bins] / np.double(bins_per_octave))

    else:
        warnings.warn("If fmax is given, n_bins will be ignored", SyntaxWarning)
        n_bins = np.ceil(
            bins_per_octave * np.log2(fmax / fmin)
        )  # Calculate the number of bins
        freqs = fmin * 2.0 ** (np.r_[0:n_bins] / np.double(bins_per_octave))

    if np.max(freqs) > fs / 2 and topbin_check == True:
        raise ValueError(
            "The top bin {}Hz has exceeded the Nyquist frequency, \
                          please reduce the n_bins".format(
                np.max(freqs)
            )
        )

    alpha = 2.0 ** (1.0 / bins_per_octave) - 1.0
    lengths = np.ceil(Q * fs / (freqs + gamma / alpha))

    # get max window length depending on gamma value
    max_len = int(max(lengths))
    fftLen = int(2 ** (np.ceil(np.log2(max_len))))

    tempKernel = np.zeros((int(n_bins), int(fftLen)), dtype=np.complex64)
    specKernel = np.zeros((int(n_bins), int(fftLen)), dtype=np.complex64)

    for k in range(0, int(n_bins)):
        freq = freqs[k]
        l = lengths[k]

        # Centering the kernels
        if l % 2 == 1:  # pad more zeros on RHS
            start = int(np.ceil(fftLen / 2.0 - l / 2.0)) - 1
        else:
            start = int(np.ceil(fftLen / 2.0 - l / 2.0))

        window_dispatch = get_window_dispatch(window, int(l), fftbins=True)
        sig = (
            window_dispatch
            * np.exp(np.r_[-l // 2 : l // 2] * 1j * 2 * np.pi * freq / fs)
            / l
        )

        if norm:  # Normalizing the filter # Trying to normalize like librosa
            tempKernel[k, start : start + int(l)] = sig / np.linalg.norm(sig, norm)
        else:
            tempKernel[k, start : start + int(l)] = sig
        # specKernel[k, :] = fft(tempKernel[k])

    # return specKernel[:,:fftLen//2+1], fftLen, torch.tensor(lenghts).float()
    return tempKernel, fftLen, torch.tensor(lengths).float(), freqs


def get_window_dispatch(window, N, fftbins=True):
    if isinstance(window, str):
        return get_window(window, N, fftbins=fftbins)
    elif isinstance(window, tuple):
        if window[0] == "gaussian":
            assert window[1] >= 0
            sigma = np.floor(-N / 2 / np.sqrt(-2 * np.log(10 ** (-window[1] / 20))))
            return get_window(("gaussian", sigma), N, fftbins=fftbins)
        else:
            Warning("Tuple windows may have undesired behaviour regarding Q factor")
    elif isinstance(window, float):
        Warning(
            "You are using Kaiser window with beta factor "
            + str(window)
            + ". Correct behaviour not checked."
        )
    else:
        raise Exception(
            "The function get_window from scipy only supports strings, tuples and floats."
        )


def create_fourier_kernels(
    n_fft,
    win_length=None,
    freq_bins=None,
    fmin=50,
    fmax=6000,
    sr=44100,
    freq_scale="linear",
    window="hann",
    verbose=True,
):
    """This function creates the Fourier Kernel for STFT, Melspectrogram and CQT.
    Most of the parameters follow librosa conventions. Part of the code comes from
    pytorch_musicnet. https://github.com/jthickstun/pytorch_musicnet

    Parameters
    ----------
    n_fft : int
        The window size

    freq_bins : int
        Number of frequency bins. Default is ``None``, which means ``n_fft//2+1`` bins

    fmin : int
        The starting frequency for the lowest frequency bin.
        If freq_scale is ``no``, this argument does nothing.

    fmax : int
        The ending frequency for the highest frequency bin.
        If freq_scale is ``no``, this argument does nothing.

    sr : int
        The sampling rate for the input audio. It is used to calculate the correct ``fmin`` and ``fmax``.
        Setting the correct sampling rate is very important for calculating the correct frequency.

    freq_scale: 'linear', 'log', 'log2', or 'no'
        Determine the spacing between each frequency bin.
        When 'linear', 'log' or 'log2' is used, the bin spacing can be controlled by ``fmin`` and ``fmax``.
        If 'no' is used, the bin will start at 0Hz and end at Nyquist frequency with linear spacing.

    Returns
    -------
    wsin : numpy.array
        Imaginary Fourier Kernel with the shape ``(freq_bins, 1, n_fft)``

    wcos : numpy.array
        Real Fourier Kernel with the shape ``(freq_bins, 1, n_fft)``

    bins2freq : list
        Mapping each frequency bin to frequency in Hz.

    binslist : list
        The normalized frequency ``k`` in digital domain.
        This ``k`` is in the Discrete Fourier Transform equation $$

    """

    if freq_bins == None:
        freq_bins = n_fft // 2 + 1
    if win_length == None:
        win_length = n_fft

    s = np.arange(0, n_fft, 1.0)
    wsin = np.empty((freq_bins, 1, n_fft))
    wcos = np.empty((freq_bins, 1, n_fft))
    start_freq = fmin
    end_freq = fmax
    bins2freq = []
    binslist = []

    # num_cycles = start_freq*d/44000.
    # scaling_ind = np.log(end_freq/start_freq)/k

    # Choosing window shape

    window_mask = get_window(window, int(win_length), fftbins=True)
    window_mask = pad_center(window_mask, n_fft)

    if freq_scale == "linear":
        if verbose == True:
            print(
                f"sampling rate = {sr}. Please make sure the sampling rate is correct in order to"
                f"get a valid freq range"
            )
        start_bin = start_freq * n_fft / sr
        scaling_ind = (end_freq - start_freq) * (n_fft / sr) / freq_bins

        for k in range(freq_bins):  # Only half of the bins contain useful info
            # print("linear freq = {}".format((k*scaling_ind+start_bin)*sr/n_fft))
            bins2freq.append((k * scaling_ind + start_bin) * sr / n_fft)
            binslist.append((k * scaling_ind + start_bin))
            wsin[k, 0, :] = np.sin(
                2 * np.pi * (k * scaling_ind + start_bin) * s / n_fft
            )
            wcos[k, 0, :] = np.cos(
                2 * np.pi * (k * scaling_ind + start_bin) * s / n_fft
            )

    elif freq_scale == "log":
        if verbose == True:
            print(
                f"sampling rate = {sr}. Please make sure the sampling rate is correct in order to"
                f"get a valid freq range"
            )
        start_bin = start_freq * n_fft / sr
        scaling_ind = np.log(end_freq / start_freq) / freq_bins

        for k in range(freq_bins):  # Only half of the bins contain useful info
            # print("log freq = {}".format(np.exp(k*scaling_ind)*start_bin*sr/n_fft))
            bins2freq.append(np.exp(k * scaling_ind) * start_bin * sr / n_fft)
            binslist.append((np.exp(k * scaling_ind) * start_bin))
            wsin[k, 0, :] = np.sin(
                2 * np.pi * (np.exp(k * scaling_ind) * start_bin) * s / n_fft
            )
            wcos[k, 0, :] = np.cos(
                2 * np.pi * (np.exp(k * scaling_ind) * start_bin) * s / n_fft
            )

    elif freq_scale == "log2":
        if verbose == True:
            print(
                f"sampling rate = {sr}. Please make sure the sampling rate is correct in order to"
                f"get a valid freq range"
            )
        start_bin = start_freq * n_fft / sr
        scaling_ind = np.log2(end_freq / start_freq) / freq_bins

        for k in range(freq_bins):  # Only half of the bins contain useful info
            # print("log freq = {}".format(np.exp(k*scaling_ind)*start_bin*sr/n_fft))
            bins2freq.append(2 ** (k * scaling_ind) * start_bin * sr / n_fft)
            binslist.append((2 ** (k * scaling_ind) * start_bin))
            wsin[k, 0, :] = np.sin(
                2 * np.pi * (2 ** (k * scaling_ind) * start_bin) * s / n_fft
            )
            wcos[k, 0, :] = np.cos(
                2 * np.pi * (2 ** (k * scaling_ind) * start_bin) * s / n_fft
            )

    elif freq_scale == "no":
        for k in range(freq_bins):  # Only half of the bins contain useful info
            bins2freq.append(k * sr / n_fft)
            binslist.append(k)
            wsin[k, 0, :] = np.sin(2 * np.pi * k * s / n_fft)
            wcos[k, 0, :] = np.cos(2 * np.pi * k * s / n_fft)
    else:
        print("Please select the correct frequency scale, 'linear' or 'log'")
    return (
        wsin.astype(np.float32),
        wcos.astype(np.float32),
        bins2freq,
        binslist,
        window_mask.astype(np.float32),
    )


class CQTCausal(nn.Module):
    """
    This algorithm is using the resampling method proposed in [1].
    Instead of convoluting the STFT results with a gigantic CQT kernel covering the full frequency
    spectrum, we make a small CQT kernel covering only the top octave.
    Then we keep downsampling the input audio by a factor of 2 to convoluting it with the
    small CQT kernel. Everytime the input audio is downsampled, the CQT relative to the downsampled
    input is equavalent to the next lower octave.
    The kernel creation process is still same as the 1992 algorithm. Therefore, we can reuse the code
    from the 1992 alogrithm [2]
    [1] Schörkhuber, Christian. “CONSTANT-Q TRANSFORM TOOLBOX FOR MUSIC PROCESSING.” (2010).
    [2] Brown, Judith C.C. and Miller Puckette. “An efficient algorithm for the calculation of a
    constant Q transform.” (1992).
    early downsampling factor is to downsample the input audio to reduce the CQT kernel size.
    The result with and without early downsampling are more or less the same except in the very low
    frequency region where freq < 40Hz.
    """

    def __init__(
        self,
        sr=22050,
        hop_length=512,
        fmin=32.70,
        fmax=None,
        n_bins=84,
        bins_per_octave=12,
        norm=True,
        basis_norm=1,
        window="hann",
        pad_mode="reflect",
        trainable_STFT=False,
        filter_scale=1,
        trainable_CQT=False,
        output_format="Complex",
        earlydownsample=True,
        verbose=True,
    ):
        super().__init__()

        self.norm = (
            norm  # Now norm is used to normalize the final CQT result by dividing n_fft
        )
        # basis_norm is for normalizing basis
        self.hop_length = hop_length
        self.pad_mode = pad_mode
        self.n_bins = n_bins
        self.output_format = output_format
        self.earlydownsample = (
            earlydownsample  # TODO: activate early downsampling later if possible
        )

        # This will be used to calculate filter_cutoff and creating CQT kernels
        Q = float(filter_scale) / (2 ** (1 / bins_per_octave) - 1)

        # Creating lowpass filter and make it a torch tensor
        if verbose == True:
            print("Creating low pass filter ...", end="\r")
        start = time()
        lowpass_filter = torch.tensor(
            create_lowpass_filter(
                band_center=0.5, kernelLength=256, transitionBandwidth=0.001
            )
        )

        # Broadcast the tensor to the shape that fits conv1d
        self.register_buffer("lowpass_filter", lowpass_filter[None, None, :])

        if verbose == True:
            print(
                "Low pass filter created, time used = {:.4f} seconds".format(
                    time() - start
                )
            )

        # Calculate num of filter requires for the kernel
        # n_octaves determines how many resampling requires for the CQT
        n_filters = min(bins_per_octave, n_bins)
        self.n_octaves = int(np.ceil(float(n_bins) / bins_per_octave))
        # print("n_octaves = ", self.n_octaves)

        # Calculate the lowest frequency bin for the top octave kernel
        self.fmin_t = fmin * 2 ** (self.n_octaves - 1)
        remainder = n_bins % bins_per_octave
        # print("remainder = ", remainder)

        if remainder == 0:
            # Calculate the top bin frequency
            fmax_t = self.fmin_t * 2 ** ((bins_per_octave - 1) / bins_per_octave)
        else:
            # Calculate the top bin frequency
            fmax_t = self.fmin_t * 2 ** ((remainder - 1) / bins_per_octave)

        self.fmin_t = fmax_t / 2 ** (
            1 - 1 / bins_per_octave
        )  # Adjusting the top minium bins
        if fmax_t > sr / 2:
            raise ValueError(
                "The top bin {}Hz has exceeded the Nyquist frequency, \
                              please reduce the n_bins".format(
                    fmax_t
                )
            )

        if (
            self.earlydownsample == True
        ):  # Do early downsampling if this argument is True
            if verbose == True:
                print("Creating early downsampling filter ...", end="\r")
            start = time()
            (
                sr,
                self.hop_length,
                self.downsample_factor,
                early_downsample_filter,
                self.earlydownsample,
            ) = get_early_downsample_params(
                sr, hop_length, fmax_t, Q, self.n_octaves, verbose
            )

            self.register_buffer("early_downsample_filter", early_downsample_filter)
            if verbose == True:
                print(
                    "Early downsampling filter created, \
                            time used = {:.4f} seconds".format(
                        time() - start
                    )
                )
        else:
            self.downsample_factor = 1.0

        # Preparing CQT kernels
        if verbose == True:
            print("Creating CQT kernels ...", end="\r")

        start = time()
        # print("Q = {}, fmin_t = {}, n_filters = {}".format(Q, self.fmin_t, n_filters))
        basis, self.n_fft, _, _ = create_cqt_kernels(
            Q,
            sr,
            self.fmin_t,
            n_filters,
            bins_per_octave,
            norm=basis_norm,
            topbin_check=False,
        )

        # This is for the normalization in the end
        freqs = fmin * 2.0 ** (np.r_[0:n_bins] / np.double(bins_per_octave))
        self.frequencies = freqs

        lenghts = np.ceil(Q * sr / freqs)
        lenghts = torch.tensor(lenghts).float()
        self.register_buffer("lenghts", lenghts)

        self.basis = basis
        fft_basis = fft(basis)[
            :, : self.n_fft // 2 + 1
        ]  # Convert CQT kenral from time domain to freq domain

        # These cqt_kernel is already in the frequency domain
        cqt_kernels_real = torch.tensor(fft_basis.real)
        cqt_kernels_imag = torch.tensor(fft_basis.imag)

        if verbose == True:
            print(
                "CQT kernels created, time used = {:.4f} seconds".format(time() - start)
            )

        # print("Getting cqt kernel done, n_fft = ",self.n_fft)
        # Preparing kernels for Short-Time Fourier Transform (STFT)
        # We set the frequency range in the CQT filter instead of here.

        if verbose == True:
            print("Creating STFT kernels ...", end="\r")

        start = time()
        kernel_sin, kernel_cos, self.bins2freq, _, window = create_fourier_kernels(
            self.n_fft, window="ones", freq_scale="no"
        )
        wsin = kernel_sin * window
        wcos = kernel_cos * window

        wsin = torch.tensor(wsin)
        wcos = torch.tensor(wcos)

        if verbose == True:
            print(
                "STFT kernels created, time used = {:.4f} seconds".format(
                    time() - start
                )
            )

        if trainable_STFT:
            wsin = nn.Parameter(wsin, requires_grad=trainable_STFT)
            wcos = nn.Parameter(wcos, requires_grad=trainable_STFT)
            self.register_parameter("wsin", wsin)
            self.register_parameter("wcos", wcos)
        else:
            self.register_buffer("wsin", wsin)
            self.register_buffer("wcos", wcos)

        if trainable_CQT:
            cqt_kernels_real = nn.Parameter(
                cqt_kernels_real, requires_grad=trainable_CQT
            )
            cqt_kernels_imag = nn.Parameter(
                cqt_kernels_imag, requires_grad=trainable_CQT
            )
            self.register_parameter("cqt_kernels_real", cqt_kernels_real)
            self.register_parameter("cqt_kernels_imag", cqt_kernels_imag)
        else:
            self.register_buffer("cqt_kernels_real", cqt_kernels_real)
            self.register_buffer("cqt_kernels_imag", cqt_kernels_imag)

            # If center==True, the STFT window will be put in the middle, and paddings at the beginning
        # and ending are required.
        if self.pad_mode == "constant":
            self.padding = nn.ConstantPad1d((self.n_fft, 0), 0)
        elif self.pad_mode == "reflect":
            self.padding = nn.ReflectionPad1d(self.n_fft // 2)

    def forward(self, x, output_format=None, normalization_type="librosa"):
        """
        Convert a batch of waveforms to CQT spectrograms.

        Parameters
        ----------
        x : torch tensor
            Input signal should be in either of the following shapes.\n
            1. ``(len_audio)``\n
            2. ``(num_audio, len_audio)``\n
            3. ``(num_audio, 1, len_audio)``
            It will be automatically broadcast to the right shape
        """
        output_format = output_format or self.output_format

        x = broadcast_dim(x)
        if self.earlydownsample == True:
            x = downsampling_by_n(
                x, self.early_downsample_filter, self.downsample_factor
            )
        hop = self.hop_length
        S = int(x.shape[-1] / hop) + 1
        CQT = get_cqt_complex2(
            x,
            self.cqt_kernels_real,
            self.cqt_kernels_imag,
            hop,
            self.padding,
            wcos=self.wcos,
            wsin=self.wsin,
        )

        x_down = x  # Preparing a new variable for downsampling
        k = 1
        for i in range(self.n_octaves - 1):
            if hop == 1:
                hop = hop
            else:
                hop = hop // 2
            x_down = downsampling_by_2(x_down, self.lowpass_filter)
            CQT1 = get_cqt_complex2(
                x_down,
                self.cqt_kernels_real,
                self.cqt_kernels_imag,
                hop,
                self.padding,
                wcos=self.wcos,
                wsin=self.wsin,
            )
            CQT = torch.cat((CQT1, CQT), 1)

        CQT = CQT[:, -self.n_bins :, :]  # Removing unwanted top bins

        if normalization_type == "librosa":
            CQT *= torch.sqrt(self.lenghts.view(-1, 1, 1)) / self.n_fft
        elif normalization_type == "convolutional":
            pass
        elif normalization_type == "wrap":
            CQT *= 2 / self.n_fft
        else:
            raise ValueError(
                "The normalization_type %r is not part of our current options."
                % normalization_type
            )

        if output_format == "Magnitude":
            # Getting CQT Amplitude
            return torch.sqrt(CQT.pow(2).sum(-1))

        elif output_format == "Complex":
            return CQT

        elif output_format == "Phase":
            phase_real = torch.cos(torch.atan2(CQT[:, :, :, 1], CQT[:, :, :, 0]))
            phase_imag = torch.sin(torch.atan2(CQT[:, :, :, 1], CQT[:, :, :, 0]))
            return torch.stack((phase_real, phase_imag), -1)

    def extra_repr(self) -> str:
        return "STFT kernel size = {}, CQT kernel size = {}".format(
            (*self.wcos.shape,), (*self.cqt_kernels_real.shape,)
        )
