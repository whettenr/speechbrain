"""Branchformer implementation.

Ref: "Branchformer: Parallel MLP-Attention Architectures
to Capture Local and Global Context for Speech Recognition and Understanding"

Source: Some parts of the code may be adapted from ESPNet.

Authors
* Titouan Parcollet 2023
"""

import torch
import torch.nn as nn
from typing import Optional
import numpy as np


from speechbrain.nnet.attention import RelPosMHAXL, MultiheadAttention
from speechbrain.nnet.normalization import LayerNorm
from speechbrain.lobes.models.convolution import ConvolutionalSpatialGatingUnit
from speechbrain.nnet.hypermixing import HyperMixing
from speechbrain.nnet.attention import Fastattention
from speechbrain.lobes.models.VanillaNN import VanillaNN
from speechbrain.nnet.summary_mixing import SummaryMixing


class ConvolutionBranch(nn.Module):
    """This is an implementation of the convolution branch in Branchformer.

    The default structure is:
    LN -> Channel Proj -> GeLU -> (CNN Spatial Gating) -> Channel Proj -> Dropout

    Arguments
    ----------
    input_size : int
        The expected size of the feature (channel) dimension.
    linear_units: int, optional
        Number of neurons in the hidden linear units.
    kernel_size: int, optional
        Kernel size of non-bottleneck convolutional layer.
    activation: torch.nn.Module, optional
         Activation function used after pre projection.
    gate_activation: torch.nn.Module, optional
         Activation function used at the gate of the CSGU module.
    dropout: float, optional
         Dropout rate.
    use_linear_after_conv: bool, optional
        If True, will apply a linear transformation of size input_size//2

    Example
    -------
    >>> x = torch.rand((8, 60, 512))
    >>> net = ConvolutionBranch(512, 1024)
    >>> output = net(x)
    >>> output.shape
    torch.Size([8, 60, 512])
    """

    def __init__(
        self,
        input_size,
        linear_units=3072,
        kernel_size=31,
        activation=nn.GELU,
        gate_activation=nn.Identity,
        dropout=0.0,
        use_linear_after_conv=False,
    ):
        super().__init__()

        self.pre_channel_proj = nn.Linear(input_size, linear_units)
        self.post_channel_proj = nn.Linear(linear_units // 2, input_size)
        self.activation = activation()
        self.csgu = ConvolutionalSpatialGatingUnit(
            input_size=linear_units,
            kernel_size=kernel_size,
            dropout=dropout,
            use_linear_after_conv=use_linear_after_conv,
            activation=gate_activation,
        )

    def forward(self, x):
        """
        Arguments
        ----------
        x: torch.Tensor -> (B, T, D)

        """
        x = self.activation(self.pre_channel_proj(x))  # (B, T, D)
        x = self.csgu(x)  # (B, T, D//2)
        x = self.post_channel_proj(x)  # (B, T, D)

        return x


class BranchformerEncoderLayer(nn.Module):
    """This is an implementation of Branchformer encoder layer.

    Arguments
    ----------
    d_model : int
        The expected size of the input embedding.
    nhead : int
        Number of attention heads.
    kernel_size : int, optional
        Kernel size of convolution model.
    kdim : int, optional
        Dimension of the key.
    vdim : int, optional
        Dimension of the value.
    activation: torch.nn.Module
         Activation function used in each Conformer layer.
    dropout : int, optional
        Dropout for the encoder.
    attention_type: str, optional
        type of attention layer, e.g. regulaMHA for regular MultiHeadAttention.
    csgu_linear_units: int, optional
        Number of neurons in the hidden linear units of the CSGU Module.
    gate_activation: torch.nn.Module, optional
         Activation function used at the gate of the CSGU module.
    use_linear_after_conv: bool, optional
        If True, will apply a linear transformation of size input_size//2
    local_proj_out_dim: int, optional
        The dimension of the output of the local projection branch. This
        will be concatenated with the output of the summary branch
        (default: 512).
    summary_hid_dim: list [int], optional
        A list of dimension specifying both the number of hidden layers
        as well as the size of them in the summary projection branch
        (default: [1024]).
    summary_out_dim: int, optional
        The dimension of the output of the summary projection branch. This
        will be concatenated with the output of the local branch
        (default: 1024).
    activation: torch.nn.Module, optional
        Torch module specifying the activation function used in both the local
        and summary branches.
        (default: torch.nn.GELU)
    mode: string, optional
        One of "SummaryMixing" or "SummaryMixing-lite". Changes the SummaryMixing cell
        according to the definition of the article. "SummaryMixing-lite" removes the
        local project branch.

    Example
    -------
    >>> import torch
    >>> x = torch.rand((8, 60, 512))
    >>> pos_embs = torch.rand((1, 2*60-1, 512))
    >>> net = BranchformerEncoderLayer(nhead=8, d_model=512, kernel_size=3)
    >>> output = net(x, pos_embs=pos_embs)
    >>> output[0].shape
    torch.Size([8, 60, 512])
    """

    def __init__(
        self,
        d_model,
        nhead,
        kernel_size=31,
        kdim=None,
        vdim=None,
        activation=nn.GELU,
        dropout=0.0,
        attention_type="RelPosMHAXL",
        csgu_linear_units=3072,
        gate_activation=nn.Identity,
        use_linear_after_conv=False,
        local_proj_hid_dim=[512],
        local_proj_out_dim=512,
        summary_hid_dim=[1024],
        summary_out_dim=1024,
        mode="SummaryMixing",
    ):
        super().__init__()

        self.attention_type = attention_type
        self.mode = mode

        # If CNN only, no need for the attention branch and merging
        if self.attention_type != "cnnonly":
            if attention_type == "regularMHA":
                self.mha_layer = MultiheadAttention(
                    nhead=nhead, d_model=d_model, dropout=dropout, kdim=kdim, vdim=vdim,
                )
                self.merge_proj = torch.nn.Linear(d_model * 2, d_model)
            elif attention_type == "RelPosMHAXL":
                # transformerXL style positional encoding
                self.mha_layer = RelPosMHAXL(
                    num_heads=nhead,
                    embed_dim=d_model,
                    dropout=dropout,
                    mask_pos_future=False,
                )
                self.merge_proj = torch.nn.Linear(d_model * 2, d_model)
            elif attention_type == "hypermixing":
                self.mha_layer = HyperMixing(
                    input_output_dim=d_model,
                    hypernet_size=local_proj_hid_dim[0],
                    tied=False,
                    num_heads=nhead,
                    fix_tm_hidden_size=False,
                )
                self.merge_proj = torch.nn.Linear(d_model * 2, d_model)

            elif attention_type == "SummaryMixing":
                self.mha_layer = SummaryMixing(
                    enc_dim=d_model,
                    nhead=nhead,
                    local_proj_hid_dim=local_proj_hid_dim,
                    local_proj_out_dim=local_proj_out_dim,
                    summary_hid_dim=summary_hid_dim,
                    summary_out_dim=summary_out_dim,
                    activation=activation,
                    mode=mode,
                )
                self.merge_dnn_blocks = summary_hid_dim + [d_model]
                self.merge_proj = VanillaNN(
                    input_shape=[None, None, local_proj_out_dim + summary_out_dim],
                    dnn_blocks=len(self.merge_dnn_blocks),
                    dnn_neurons=self.merge_dnn_blocks,
                    activation=activation,
                )
            elif attention_type == "fastattention":
                self.mha_layer = Fastattention(
                    enc_dim=d_model,
                    nhead=nhead,
                    dropout=dropout,
                )
                self.merge_proj = torch.nn.Linear(d_model * 2, d_model)

            self.norm_mhsa = LayerNorm(d_model)

        self.convolution_branch = ConvolutionBranch(
            input_size=d_model,
            kernel_size=kernel_size,
            linear_units=csgu_linear_units,
            activation=activation,
            gate_activation=gate_activation,
            dropout=dropout,
            use_linear_after_conv=use_linear_after_conv,
        )

        self.norm_conv = LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x,
        src_mask: Optional[torch.Tensor] = None,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        pos_embs: Optional[torch.Tensor] = None,
    ):
        """
        Arguments
        ----------
        x : torch.Tensor
            The sequence to the encoder layer.
        src_mask : torch.Tensor, optional
            The mask for the src sequence.
        src_key_padding_mask : torch.Tensor, optional
            The mask for the src keys per batch.
        pos_embs: torch.Tensor, torch.nn.Module, optional
            Module or tensor containing the input sequence positional embeddings
        """
        if self.attention_type == "cnnonly":
            x2 = x
            x2 = self._forward_cnn_branch(x2)
            x = x + x2
            self_attn = None
        else:
            x1 = x
            x2 = x
            # Branch 1: Self-attention
            x1, self_attn = self._forward_mha_branch(
                x1, src_mask, src_key_padding_mask, pos_embs
            )

            # Branch 2: Convolutional gating MLP
            # In ESPnet, masks are not used?! we do the same but warning!
            x2 = self._forward_cnn_branch(x2)

            x = x + self.dropout(self.merge_proj(torch.cat([x1, x2], dim=-1)))

        return x, self_attn

    def _forward_cnn_branch(
        self, x,
    ):
        """
        Arguments
        ----------
        x : torch.Tensor
            The sequence to the encoder layer.
        """
        x = self.norm_conv(x)
        x = self.convolution_branch(x)

        return self.dropout(x)

    def _forward_mha_branch(
        self,
        x,
        src_mask: Optional[torch.Tensor] = None,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        pos_embs: Optional[torch.Tensor] = None,
    ):
        """
        Arguments
        ----------
        x : torch.Tensor
            The sequence to the encoder layer.
        src_mask : torch.Tensor, optional
            The mask for the src sequence.
        src_key_padding_mask : torch.Tensor, optional
            The mask for the src keys per batch.
        pos_embs: torch.Tensor, torch.nn.Module, optional
            Module or tensor containing the input sequence positional embeddings
        """

        x = self.norm_mhsa(x)

        if self.attention_type == "SummaryMixing":
            x = self.mha_layer(x, attention_mask=src_key_padding_mask)
            self_attn = None
        else:
            x, self_attn = self.mha_layer(
                x,
                x,
                x,
                attn_mask=src_mask,
                key_padding_mask=src_key_padding_mask,
                pos_embs=pos_embs,
            )

        return self.dropout(x), self_attn


class BranchformerEncoder(nn.Module):
    """This class implements the Branchformer encoder.

    Arguments
    ---------
    num_layers : int
        Number of layers.
    d_model : int
        Embedding dimension size.
    nhead : int
        Number of attention heads.
    kernel_size : int, optional
        Kernel size of convolution model.
    kdim : int, optional
        Dimension of the key.
    vdim : int, optional
        Dimension of the value.
    activation: torch.nn.Module
         Activation function used in each Confomer layer.
    dropout : int, optional
        Dropout for the encoder.
    attention_type: str, optional
        type of attention layer, e.g. SummaryMixing or regulaMHA for regular MultiHeadAttention.
    csgu_linear_units: int, optional
        Number of neurons in the hidden linear units of the CSGU Module.
    gate_activation: torch.nn.Module, optional
         Activation function used at the gate of the CSGU module.
    use_linear_after_conv: bool, optional
        If True, will apply a linear transformation of size input_size//2.
    local_proj_out_dim: int, optional
        The dimension of the output of the local projection branch. This
        will be concatenated with the output of the summary branch
        (default: 512).
    summary_hid_dim: list [int], optional
        A list of dimension specifying both the number of hidden layers
        as well as the size of them in the summary projection branch
        (default: [1024]).
    summary_out_dim: int, optional
        The dimension of the output of the summary projection branch. This
        will be concatenated with the output of the local branch
        (default: 1024).
    activation: torch.nn.Module, optional
        Torch module specifying the activation function used in both the local
        and summary branches.
        (default: torch.nn.GELU)
    mode: string, optional
        One of "SummaryMixing" or "SummaryMixing-lite". Changes the SummaryMixing cell
        according to the definition of the article. "SummaryMixing-lite" removes the
        local project branch.


    Example
    -------
    >>> import torch
    >>> x = torch.rand((8, 60, 512))
    >>> pos_emb = torch.rand((1, 2*60-1, 512))
    >>> net = BranchformerEncoder(1, 512, 8)
    >>> output, _ = net(x, pos_embs=pos_emb)
    >>> output.shape
    torch.Size([8, 60, 512])
    """

    def __init__(
        self,
        num_layers,
        d_model,
        nhead,
        kernel_size=31,
        kdim=None,
        vdim=None,
        activation=nn.GELU,
        dropout=0.0,
        attention_type="RelPosMHAXL",
        csgu_linear_units=3072,
        gate_activation=nn.Identity,
        use_linear_after_conv=False,
        local_proj_hid_dim=[512],
        local_proj_out_dim=512,
        summary_hid_dim=[1024],
        summary_out_dim=1024,
        mode="SummaryMixing",
        output_hidden_states=False,
        layerdrop_prob=0.0,
    ):
        super().__init__()

        self.layers = torch.nn.ModuleList(
            [
                BranchformerEncoderLayer(
                    nhead=nhead,
                    d_model=d_model,
                    kdim=kdim,
                    vdim=vdim,
                    dropout=dropout,
                    activation=activation,
                    kernel_size=kernel_size,
                    attention_type=attention_type,
                    csgu_linear_units=csgu_linear_units,
                    gate_activation=gate_activation,
                    use_linear_after_conv=use_linear_after_conv,
                    local_proj_hid_dim=local_proj_hid_dim,
                    local_proj_out_dim=local_proj_out_dim,
                    summary_hid_dim=summary_hid_dim,
                    summary_out_dim=summary_out_dim,
                    mode=mode,
                )
                for i in range(num_layers)
            ]
        )
        self.norm = LayerNorm(d_model, eps=1e-6)
        self.attention_type = attention_type
        self.layerdrop_prob = layerdrop_prob
        self.rng = np.random.default_rng()
        self.output_hidden_states = output_hidden_states

    def forward(
        self,
        src,
        src_mask: Optional[torch.Tensor] = None,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        pos_embs: Optional[torch.Tensor] = None,
        dynchunktrain_config=None,
    ):
        """
        Arguments
        ----------
        src : torch.Tensor
            The sequence to the encoder layer.
        src_mask : torch.Tensor, optional
            The mask for the src sequence.
        src_key_padding_mask : torch.Tensor, optional
            The mask for the src keys per batch.
        pos_embs: torch.Tensor, torch.nn.Module,
            Module or tensor containing the input sequence positional embeddings
            If custom pos_embs are given it needs to have the shape (1, 2*S-1, E)
            where S is the sequence length, and E is the embedding dimension.
        """
        assert (
            dynchunktrain_config is None
        ), "Dynamic Chunk Training unsupported for this encoder"

        if self.attention_type == "RelPosMHAXL":
            if pos_embs is None:
                raise ValueError(
                    "The chosen attention type for the Branchformer is RelPosMHAXL. For this attention type, the positional embeddings are mandatory"
                )

        output = src
        if self.layerdrop_prob > 0.0:
            keep_probs = self.rng.random(len(self.layers))
            # print('probs: ', keep_probs)
        else:
            keep_probs = None

        attention_lst = []
        if self.output_hidden_states:
            hidden_state_lst = [output]

        for i, enc_layer in enumerate(self.layers):
            if (
                not self.training
                or self.layerdrop_prob == 0.0
                or keep_probs[i] > self.layerdrop_prob
            ):
                # print('going through layer: ', i)
                output, attention = enc_layer(
                    output,
                    src_mask=src_mask,
                    src_key_padding_mask=src_key_padding_mask,
                    pos_embs=pos_embs,
                )
                attention_lst.append(attention)

                if self.output_hidden_states:
                    hidden_state_lst.append(output)
        
        output = self.norm(output)
        if self.output_hidden_states:
            return output, attention_lst, hidden_state_lst
        return output, attention_lst