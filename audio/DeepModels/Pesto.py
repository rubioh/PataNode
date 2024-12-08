import nnAudio.features
import numpy as np
import torch
import torch.nn as nn

from typing import Optional
from functools import partial

#from audio.DeepModels.CQTCausal import CQTCausal


class PESTO(nn.Module):
    def __init__(self, device=None):
        super(PESTO, self).__init__()
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda:0"
            else:
                self.device = "cpu"
        else:
            self.device = device

        if self.device == "cuda:0":
            self.force_cudnn_init()

        self.module = Resnet1d(
            n_chan_input=1,
            n_chan_layers=(40, 30, 30, 10, 3),
            n_prefilt_layers=4,
            residual=True,
            n_bins_in=264,  # 264,
            bins_per_semitone=1,
            num_output_layers=1,
            output_dim=384,  # 384,
            a_lrelu=0.3,
            p_dropout=0.2,
            downsampling="stride",
            final_norm="softmax",
        ).to(self.device)

        cqt_kwargs = dict(
            fmin=26.46115551458899,
            fmax=None,
            n_bins=297,  # 297,
            bins_per_octave=36,
            hop_length=256,
            pad_mode="constant",
        )

#       sd = torch.load('weights.ckpt')['state_dict']
#       sd = torch.load('audio/DeepModels/weights.ckpt')['state_dict']
        sd = torch.load("audio/DeepModels/last.ckpt")["state_dict"]
#       sd = torch.load('audio/DeepModels/weights_140.ckpt')['state_dict']
        self.load_state_dict(sd)
#       self.get_CQT = CQTCausal(sr=16000,
        self.get_CQT = nnAudio.features.CQT(
            sr=16000, output_format="Complex", **cqt_kwargs
        ).to(self.device)

        self.i = 0
        self.prev_pesto_info = 0
        self.pesto_info = 0

    def force_cudnn_init(self):
        s = 32
        dev = torch.device("cuda")
        torch.nn.functional.conv2d(
            torch.zeros(s, s, s, s, device=dev), torch.zeros(s, s, s, s, device=dev)
        )

    def save(self, x):
        self.i += 1
        np.save(
            "/media/mathieu/y/Data/CQT_outlier/" + str(self.i),
            x.cpu().unsqueeze(0).detach().numpy(),
        )

    def forward(self, x):
        x = torch.FloatTensor(x).to(self.device)
        out = self.get_CQT(x)
#       self.save(out[0, :, -1].unsqueeze(0))
        out = torch.view_as_complex(out)
        cqt = torch.abs(out[0])
        out = cqt[17 + 16 :, :].transpose(0, 1).unsqueeze(1)
        out = self.module(out)
        out = out[-1]
#       out = out[0]*(1.-(.5+.3333)) + .3333*out[1] + .5*out[2]
        return out.to("cpu").detach().numpy(), cqt.to("cpu")[:, -1].detach().numpy()

    def get_features(self, x, D):
        if x.shape[0] < 17000:
            return {"pitch": 0}

        pesto_info, cqt = self.forward(x.reshape(1, -1))

        if D["dsmooth_low"] > 0.01:
            pesto_info = self.prev_pesto_info

        self.prev_pesto_info = pesto_info
        am = np.argmax(pesto_info)

        self.pesto_info = 0.1 * self.pesto_info + 0.9 * am
        return {"cqt": cqt, "pitch": self.pesto_info}


class ToeplitzLinear(nn.Conv1d):
    def __init__(self, in_features, out_features):
        super(ToeplitzLinear, self).__init__(
            in_channels=1,
            out_channels=1,
            kernel_size=in_features + out_features - 1,
            padding=out_features - 1,
            bias=False,
        )

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        return super(ToeplitzLinear, self).forward(input.unsqueeze(-2)).squeeze(-2)


class Resnet1d(nn.Module):
    """
    Basic CNN similar to the one in Johannes Zeitler's report,
    but for longer HCQT input (always stride 1 in time)
    Still with 75 (-1) context frames, i.e. 37 frames padded to each side
    The number of input channels, channels in the hidden layers, and output
    dimensions (e.g. for pitch output) can be parameterized.
    Layer normalization is only performed over frequency and channel dimensions,
    not over time (in order to work with variable length input).
    Outputs one channel with sigmoid activation.

    Args (Defaults: BasicCNN by Johannes Zeitler but with 6 input channels):
        n_chan_input:     Number of input channels (harmonics in HCQT)
        n_chan_layers:    Number of channels in the hidden layers (list)
        n_prefilt_layers: Number of repetitions of the prefiltering layer
        residual:         If True, use residual connections for prefiltering (default: False)
        n_bins_in:        Number of input bins (12 * number of octaves)
        n_bins_out:       Number of output bins (12 for pitch class, 72 for pitch, num_octaves * 12)
        a_lrelu:          alpha parameter (slope) of LeakyReLU activation function
        p_dropout:        Dropout probability
    """

    def __init__(
        self,
        n_chan_input=6,
        n_chan_layers=(20, 20, 10, 1),
        n_prefilt_layers=1,
        residual=False,
        n_bins_in=216,
        bins_per_semitone: Optional[int] = None,
        n_bins_out: Optional[int] = None,
        output_dim=128,
        num_output_layers: int = 1,
        activation_fn: str = "leaky",
        a_lrelu=0.3,
        p_dropout=0.2,
        downsampling: str = "stride",
        final_norm="none",
        final_fc: str = "toeplitz",  # useful only for ablation studies, you should keep default value
    ):
        super(Resnet1d, self).__init__()

        if activation_fn == "relu":
            activation_layer = nn.ReLU
        elif activation_fn == "silu":
            activation_layer = nn.SiLU
        elif activation_fn == "leaky":
            activation_layer = partial(nn.LeakyReLU, negative_slope=a_lrelu)
        else:
            raise ValueError

        n_in = n_chan_input
        n_ch = n_chan_layers

        if len(n_ch) < 5:
            n_ch.append(1)

        assert bins_per_semitone or n_bins_out, "Specify one of them"
        if bins_per_semitone is None:
            bins_per_semitone = n_bins_in // n_bins_out
        elif n_bins_out is None:
            n_bins_out = n_bins_in // bins_per_semitone
        self.bins_per_semitone = bins_per_semitone
        last_kernel_size = n_bins_in // bins_per_semitone + 1 - n_bins_out

        # Layer normalization over frequency and channels (harmonics of HCQT)
        self.layernorm = nn.LayerNorm(normalized_shape=[n_in, n_bins_in])

        # Prefiltering
        self.conv1 = nn.Sequential(
            nn.Conv1d(
                in_channels=n_in,
                out_channels=n_ch[0],
                kernel_size=15,
                padding=7,
                stride=1,
            ),
            activation_layer(),
            nn.Dropout(p=p_dropout),
        )
        self.n_prefilt_layers = n_prefilt_layers
        self.prefilt_list = nn.ModuleList()

        for p in range(1, n_prefilt_layers):
            self.prefilt_list.append(
                nn.Sequential(
                    nn.Conv1d(
                        in_channels=n_ch[0],
                        out_channels=n_ch[0],
                        kernel_size=15,
                        padding=7,
                        stride=1,
                    ),
                    activation_layer(),
                    nn.Dropout(p=p_dropout),
                )
            )

        self.residual = residual

        # Binning to MIDI pitches
        if downsampling == "stride":
            self.conv2 = nn.Sequential(
                nn.Conv1d(
                    in_channels=n_ch[0],
                    out_channels=n_ch[1],
                    kernel_size=bins_per_semitone,
                    stride=bins_per_semitone,
                    padding=0,
                ),
                activation_layer(),
                nn.Dropout(p=p_dropout),
            )
        elif downsampling == "maxpool":
            self.conv2 = nn.Sequential(
                nn.Conv1d(
                    in_channels=n_ch[0],
                    out_channels=n_ch[1],
                    kernel_size=bins_per_semitone,
                    padding=(bins_per_semitone - 1)
                    // 2,  # WARNING: may not work if bins per semitone is even
                    stride=1,
                ),
                activation_layer(),
                nn.MaxPool1d(
                    kernel_size=bins_per_semitone, stride=bins_per_semitone, padding=0
                ),
                nn.Dropout(p=p_dropout),
            )
        else:
            raise NotImplementedError("Only stride or maxpool")

        # Time reduction
        self.conv3 = nn.Sequential(
            nn.Conv1d(
                in_channels=n_ch[1],
                out_channels=n_ch[2],
                kernel_size=1,
                padding=0,
                stride=1,
            ),
            activation_layer(),
            nn.Dropout(p=p_dropout),
        )

        # Chroma reduction
        self.conv4 = nn.Sequential(
            nn.Conv1d(
                in_channels=n_ch[2],
                out_channels=n_ch[3],
                kernel_size=1,
                padding=0,
                stride=1,
            ),
            activation_layer(),
            nn.Dropout(p=p_dropout),
            nn.Conv1d(
                in_channels=n_ch[3],
                out_channels=n_ch[4],
                kernel_size=last_kernel_size,
                padding=0,
                stride=1,
            ),
        )

        self.flatten = nn.Flatten(start_dim=1)

        layers = []
        pre_fc_dim = n_bins_out * n_ch[4]

        for i in range(num_output_layers - 1):
            layers.extend(
                [
                    ToeplitzLinear(pre_fc_dim, pre_fc_dim),
                    activation_layer(),
                    nn.Dropout(p=p_dropout),
                ]
            )

        self.pre_fc = nn.Sequential(*layers)

        if final_fc == "toeplitz":
            self.fc = ToeplitzLinear(pre_fc_dim, output_dim)
        elif final_fc == "linear":
            self.fc = nn.Linear(pre_fc_dim, output_dim)

        if final_norm == "softmax":
            self.final_norm = nn.Softmax(dim=-1)
        elif final_norm == "sigmoid":  # this shit returns nan in gradients, don't use it
            self.final_norm = nn.Sigmoid()
        elif final_norm == "none":
            self.final_norm = nn.Identity()
        else:
            raise ValueError

    def forward(self, x):
        r"""

        Args:
            x (torch.Tensor): shape (batch, channels, freq_bins)
        """
        x_norm = self.layernorm(x)
        x = self.conv1(x_norm)

        for p in range(0, self.n_prefilt_layers - 1):
            prefilt_layer = self.prefilt_list[p]

            if self.residual:
                x_new = prefilt_layer(x)
                x = x_new + x
            else:
                x = prefilt_layer(x)

        conv2_lrelu = self.conv2(x)
        conv3_lrelu = self.conv3(conv2_lrelu)

        y_pred = self.conv4(conv3_lrelu)
        y_pred = self.flatten(y_pred)
        y_pred = self.pre_fc(y_pred)
        y_pred = self.fc(y_pred)  # WARNING: issues when batch size = 1
        return self.final_norm(y_pred)


if __name__ == "__main__":
    model = PESTO(device="cuda:0")

    import time

    x = torch.randn(1, 17000)

    for i in range(10):
        tic = time.time()
        print(model(x).shape)
        print(time.time() - tic)
