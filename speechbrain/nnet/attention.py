"""Library implementing attention modules.

Authors
 * Ju-Chieh Chou 2020
 * Jianyuan Zhong 2020
 * Loren Lugosch 2020
 * Samuele Cornell 2020
"""

import logging
import math
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from speechbrain.dataio.dataio import length_to_mask

logger = logging.getLogger(__name__)


class ContentBasedAttention(nn.Module):
    """This class implements content-based attention module for seq2seq
    learning.

    Reference: NEURAL MACHINE TRANSLATION BY JOINTLY LEARNING TO ALIGN
    AND TRANSLATE, Bahdanau et.al. https://arxiv.org/pdf/1409.0473.pdf

    Arguments
    ---------
    enc_dim : int
        Size of encoder layer.
    dec_dim : int
        Size of decoder layer.
    attn_dim : int
        Size of the attention feature.
    output_dim : int
        Size of the output context vector.
    scaling : float
        The factor controls the sharpening degree (default: 1.0).

    Example
    -------
    >>> enc_tensor = torch.rand([4, 10, 20])
    >>> enc_len = torch.ones([4]) * 10
    >>> dec_tensor = torch.rand([4, 25])
    >>> net = ContentBasedAttention(enc_dim=20, dec_dim=25, attn_dim=30, output_dim=5)
    >>> out_tensor, out_weight = net(enc_tensor, enc_len, dec_tensor)
    >>> out_tensor.shape
    torch.Size([4, 5])
    """

    def __init__(self, enc_dim, dec_dim, attn_dim, output_dim, scaling=1.0):
        super().__init__()

        self.mlp_enc = nn.Linear(enc_dim, attn_dim)
        self.mlp_dec = nn.Linear(dec_dim, attn_dim)
        self.mlp_attn = nn.Linear(attn_dim, 1, bias=False)
        self.mlp_out = nn.Linear(enc_dim, output_dim)

        self.scaling = scaling

        self.softmax = nn.Softmax(dim=-1)

        # reset the encoder states, lengths and masks
        self.reset()

    def reset(self):
        """Reset the memory in the attention module."""
        self.enc_len = None
        self.precomputed_enc_h = None
        self.mask = None

    def forward(self, enc_states, enc_len, dec_states):
        """Returns the output of the attention module.

        Arguments
        ---------
        enc_states : torch.Tensor
            The tensor to be attended.
        enc_len : torch.Tensor
            The real length (without padding) of enc_states for each sentence.
        dec_states : torch.Tensor
            The query tensor.

        Returns
        -------
        The output of the attention module.
        """

        if self.precomputed_enc_h is None:
            self.precomputed_enc_h = self.mlp_enc(enc_states)
            self.mask = length_to_mask(
                enc_len, max_len=enc_states.size(1), device=enc_states.device
            )

        dec_h = self.mlp_dec(dec_states.unsqueeze(1))
        attn = self.mlp_attn(
            torch.tanh(self.precomputed_enc_h + dec_h)
        ).squeeze(-1)

        # mask the padded frames
        attn = attn.masked_fill(self.mask == 0, -np.inf)
        attn = self.softmax(attn * self.scaling)

        # compute context vectors
        # [B, 1, L] X [B, L, F]
        context = torch.bmm(attn.unsqueeze(1), enc_states).squeeze(1)
        context = self.mlp_out(context)

        return context, attn


class LocationAwareAttention(nn.Module):
    """This class implements location-aware attention module for seq2seq learning.

    Reference: Attention-Based Models for Speech Recognition, Chorowski et.al.
    https://arxiv.org/pdf/1506.07503.pdf

    Arguments
    ---------
    enc_dim : int
        Size of encoder.
    dec_dim : int
        Size of decoder.
    attn_dim : int
        Size of the attention feature.
    output_dim : int
        Size of the output context vector.
    conv_channels : int
        Number of channel for location feature.
    kernel_size : int
        Kernel size of convolutional layer for location feature.
    scaling : float
        The factor controls the sharpening degree (default: 1.0).

    Example
    -------
    >>> enc_tensor = torch.rand([4, 10, 20])
    >>> enc_len = torch.ones([4]) * 10
    >>> dec_tensor = torch.rand([4, 25])
    >>> net = LocationAwareAttention(
    ...     enc_dim=20,
    ...     dec_dim=25,
    ...     attn_dim=30,
    ...     output_dim=5,
    ...     conv_channels=10,
    ...     kernel_size=100)
    >>> out_tensor, out_weight = net(enc_tensor, enc_len, dec_tensor)
    >>> out_tensor.shape
    torch.Size([4, 5])
    """

    precomputed_enc_h: Optional[torch.Tensor]

    def __init__(
        self,
        enc_dim,
        dec_dim,
        attn_dim,
        output_dim,
        conv_channels,
        kernel_size,
        scaling=1.0,
    ):
        super().__init__()

        self.mlp_enc = nn.Linear(enc_dim, attn_dim)
        self.mlp_dec = nn.Linear(dec_dim, attn_dim)
        self.mlp_attn = nn.Linear(attn_dim, 1, bias=False)
        self.conv_loc = nn.Conv1d(
            1,
            conv_channels,
            kernel_size=2 * kernel_size + 1,
            padding=kernel_size,
            bias=False,
        )
        self.mlp_loc = nn.Linear(conv_channels, attn_dim)
        self.mlp_attn = nn.Linear(attn_dim, 1, bias=False)
        self.mlp_out = nn.Linear(enc_dim, output_dim)

        self.scaling = scaling

        self.softmax = nn.Softmax(dim=-1)

        # reset the encoder states, lengths and masks
        self.reset()

    def reset(self):
        """Reset the memory in attention module."""
        self.enc_len = None
        self.precomputed_enc_h = None
        self.mask = None
        self.prev_attn = None

    def forward(self, enc_states, enc_len, dec_states):
        """Returns the output of the attention module.

        Arguments
        ---------
        enc_states : torch.Tensor
            The tensor to be attended.
        enc_len : torch.Tensor
            The real length (without padding) of enc_states for each sentence.
        dec_states : torch.Tensor
            The query tensor.

        Returns
        -------
        The output of the attention module.
        """
        if self.precomputed_enc_h is None:
            self.precomputed_enc_h = self.mlp_enc(enc_states)
            self.mask = length_to_mask(
                enc_len, max_len=enc_states.size(1), device=enc_states.device
            )

            # multiply mask by 1/Ln for each row
            self.prev_attn = self.mask * (1 / enc_len.float()).unsqueeze(1)

        # compute location-aware features
        # [B, 1, L] -> [B, C, L]
        attn_conv = self.conv_loc(self.prev_attn.unsqueeze(1))
        # [B, C, L] -> [B, L, C] -> [B, L, F]
        attn_conv = self.mlp_loc(attn_conv.transpose(1, 2))

        dec_h = self.mlp_dec(dec_states.unsqueeze(1))
        attn = self.mlp_attn(
            torch.tanh(self.precomputed_enc_h + dec_h + attn_conv)
        ).squeeze(-1)

        # mask the padded frames
        attn = attn.masked_fill(self.mask == 0, -np.inf)
        attn = self.softmax(attn * self.scaling)

        # set prev_attn to current attn for the next timestep
        self.prev_attn = attn.detach()

        # compute context vectors
        # [B, 1, L] X [B, L, F]
        context = torch.bmm(attn.unsqueeze(1), enc_states).squeeze(1)
        context = self.mlp_out(context)

        return context, attn


class KeyValueAttention(nn.Module):
    """This class implements a single-headed key-value attention module for seq2seq
    learning.

    Reference: "Attention Is All You Need" by Vaswani et al., sec. 3.2.1

    Arguments
    ---------
    enc_dim : int
        Size of the encoder feature vectors from which keys and values are computed.
    dec_dim : int
        Size of the decoder feature vectors from which queries are computed.
    attn_dim : int
        Size of the attention feature.
    output_dim : int
        Size of the output context vector.

    Example
    -------
    >>> enc_tensor = torch.rand([4, 10, 20])
    >>> enc_len = torch.ones([4]) * 10
    >>> dec_tensor = torch.rand([4, 25])
    >>> net = KeyValueAttention(enc_dim=20, dec_dim=25, attn_dim=30, output_dim=5)
    >>> out_tensor, out_weight = net(enc_tensor, enc_len, dec_tensor)
    >>> out_tensor.shape
    torch.Size([4, 5])
    """

    def __init__(self, enc_dim, dec_dim, attn_dim, output_dim):
        super().__init__()

        self.key_linear = nn.Linear(enc_dim, attn_dim)
        self.query_linear = nn.Linear(dec_dim, attn_dim)
        self.value_linear = nn.Linear(enc_dim, output_dim)
        self.scaling = torch.sqrt(torch.tensor(attn_dim).float())

        # reset the encoder states, lengths and masks
        self.reset()

    def reset(self):
        """Reset the memory in the attention module."""
        self.values = None
        self.keys = None
        self.mask = None

    def forward(self, enc_states, enc_len, dec_states):
        """Returns the output of the attention module.

        Arguments
        ---------
        enc_states : torch.Tensor
            The tensor to be attended.
        enc_len : torch.Tensor
            The real length (without padding) of enc_states for each sentence.
        dec_states : torch.Tensor
            The query tensor.

        Returns
        -------
        The output of the attention module.
        """

        if self.keys is None:
            self.keys = self.key_linear(enc_states)
            self.values = self.value_linear(enc_states)
            self.mask = length_to_mask(
                enc_len, max_len=enc_states.size(1), device=enc_states.device
            ).unsqueeze(2)

        query = self.query_linear(dec_states).unsqueeze(2)
        scores = torch.matmul(self.keys, query) / self.scaling
        scores = scores.masked_fill(self.mask == 0, -np.inf)
        normalized_scores = scores.softmax(1).transpose(1, 2)
        out = torch.matmul(normalized_scores, self.values).squeeze(1)
        return out, normalized_scores


class RelPosEncXL(nn.Module):
    """Relative positional encoding for the :class:`~RelPosMHAXL`.

    Arguments
    ---------
    emb_dim : int
        Size of the embedding, which controls the size of the last dimension
        of the positional embedding as well
    dtype : torch.dtype, optional
        If unspecified, defaults to `torch.float32`. Controls the data type of
        the output embedding (but does not affect the precision of the
        computations, which remain `torch.float32`).
    """

    def __init__(self, emb_dim: int, dtype: torch.dtype = torch.float32):
        super().__init__()
        self.emb_dim = emb_dim

        inv_freq = torch.exp(
            torch.arange(0, self.emb_dim, 2, dtype=torch.float32)
            * -(math.log(10000.0) / self.emb_dim)
        )
        self.register_buffer("inv_freq", inv_freq)

        self.emb_dtype = dtype

    @torch.no_grad()
    def make_pe(self, seq_len: int):
        """
        Builds the positional embedding tensor for a given sequence length.

        Arguments
        ---------
        seq_len : int
            The length of the sequence to create the position embedding for.

        Returns
        -------
        torch.Tensor
            Positional embedding tensor of shape `[1, 2*seq_len-1, embed_dim]`
        """

        emb_dtype = self.emb_dtype
        device = self.inv_freq.device

        with torch.no_grad():
            # perform initialization with the same type as `inv_freq`, to enable
            # migrating the embeddings to fp16 by calling
            # `posenc.to(torch.float16)`

            tot_pe = torch.empty(
                (2, seq_len, self.emb_dim),
                dtype=torch.float32,
                device=device,
            )
            pe_past = tot_pe[0]
            pe_future = tot_pe[1]
            positions = torch.arange(
                0,
                seq_len,
                dtype=torch.float32,
                device=device,
            ).unsqueeze(-1)

            sinusoids = torch.sin(positions * self.inv_freq)
            pe_past[:, 0::2] = sinusoids
            pe_past[:, 1::2] = torch.cos(positions * self.inv_freq)
            pe_future[:, 0::2] = sinusoids  # same for past and future
            pe_future[:, 1::2] = torch.cos(-positions * self.inv_freq)

            pe_past = torch.flip(pe_past, (0,)).unsqueeze(0)
            pe_future = pe_future[1:].unsqueeze(0)
            pe = torch.cat([pe_past, pe_future], dim=1)
            pe = pe.to(emb_dtype)  # convert to type of module

        return pe

    def forward(self, x: torch.Tensor):
        """
        Builds the positional embedding tensor. Similar to
        :meth:`~RelPosEncXL.make_pe` but uses the shape information from the
        provided tensor.

        Arguments
        ---------
        x : torch.Tensor
            input tensor with shape batch_size, seq_len, embed_dim

        Returns
        -------
        pos_emb : torch.Tensor
            Positional embedding tensor of shape `[1, 2*seq_len-1, embed_dim]`
        """

        return self.make_pe(seq_len=x.size(1))


class RelPosMHAXL(nn.Module):
    """This class implements the relative multihead implementation similar to that in Transformer XL
    https://arxiv.org/pdf/1901.02860.pdf

    Arguments
    ---------
    embed_dim : int
        Size of the encoder feature vectors from which keys and values are computed.
    num_heads: int
        Number of attention heads.
    dropout : float, optional
        Dropout rate.
    vbias: bool, optional
        Whether to use bias for computing value.
    vdim: int, optional
        Size for value. Default is embed_dim (Note each head is embed_dim // num_heads).
    mask_pos_future: bool, optional
        Whether to mask future positional encodings values.
        Must be true for causal applications e.g. decoder.

    Example
    -------
    >>> inputs = torch.rand([6, 60, 512])
    >>> pos_emb = torch.rand([1, 2*60-1, 512])
    >>> net = RelPosMHAXL(num_heads=8, embed_dim=inputs.shape[-1])
    >>> outputs, attn = net(inputs, inputs, inputs, pos_emb)
    >>> outputs.shape
    torch.Size([6, 60, 512])
    """

    def __init__(
        self,
        embed_dim,
        num_heads,
        dropout=0.0,
        vbias=False,
        vdim=None,
        mask_pos_future=False,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.vdim = vdim if vdim is not None else embed_dim
        self._qkv_same_embed_dim = self.vdim == embed_dim
        self.mask_pos_future = mask_pos_future
        self.vbias = vbias

        self.num_heads = num_heads
        self.dropout = dropout
        self.head_dim = embed_dim // num_heads
        self.vhead_dim = self.vdim // num_heads

        assert (
            self.head_dim * num_heads == self.embed_dim
        ), "embed_dim must be divisible by num_heads"
        assert (
            self.vhead_dim * num_heads == self.vdim
        ), "vdim must be divisible by num_heads"

        if self._qkv_same_embed_dim is False:
            self.qk_proj_weight = nn.Parameter(
                torch.empty(2 * embed_dim, embed_dim)
            )
            self.v_proj_weight = nn.Parameter(torch.empty(self.vdim, embed_dim))
        else:
            self.in_proj_weight = nn.Parameter(
                torch.empty(3 * embed_dim, embed_dim)
            )

        if vbias:
            self.value_bias_weight = nn.Parameter(torch.empty(self.vdim))
        else:
            self.vbias = None

        self.dropout_att = nn.Dropout(dropout)
        self.out_proj = nn.Linear(self.vdim, embed_dim)

        self.linear_pos = nn.Linear(embed_dim, embed_dim, bias=False)

        self.pos_bias_u = nn.Parameter(
            torch.empty(self.head_dim, self.num_heads)
        )
        self.pos_bias_v = nn.Parameter(
            torch.empty(self.head_dim, self.num_heads)
        )

        if next(self.parameters()).dtype == torch.float16:
            self.attn_fill_value = -65000
        else:
            self.attn_fill_value = -float("inf")

        self._reset_parameters()
        self.scale = 1 / math.sqrt(self.embed_dim)

    def _reset_parameters(self):
        if self._qkv_same_embed_dim:
            torch.nn.init.xavier_uniform_(self.in_proj_weight)
        else:
            torch.nn.init.xavier_uniform_(self.qk_proj_weight)
            torch.nn.init.xavier_uniform_(self.v_proj_weight)

        if self.vbias is not None:
            torch.nn.init.constant_(self.value_bias_weight, 0.0)

        # positional biases
        torch.nn.init.xavier_uniform_(self.pos_bias_u)
        torch.nn.init.xavier_uniform_(self.pos_bias_v)

    def rel_shift(self, x):
        """Relative shift implementation."""
        # batch, head, time1, 2*time1-1.

        b, h, qlen, pos_len = x.size()  # (b, h, t1, t2)
        # need to add a column of zeros on the left side of last dimension to perform the relative shifting
        x = torch.nn.functional.pad(x, pad=(1, 0))  # (b, h, t1, t2+1)
        x = x.view(b, h, -1, qlen)  # (b, h, t2+1, t1)
        # need to drop the first row
        x = x[:, :, 1:].view(b, h, qlen, pos_len)  # (b, h, t1, t2)

        # cspell:ignore tril
        if self.mask_pos_future:
            ones = torch.ones((x.size(2), x.size(3)), device=x.device)
            x = x * torch.tril(ones, x.size(3) - x.size(2))[None, None, :, :]

        return x[..., : pos_len // 2 + 1]

    def forward(
        self,
        query,
        key,
        value,
        pos_embs,
        key_padding_mask=None,
        attn_mask=None,
        return_attn_weights=True,
    ):
        """Compute attention.

        Arguments
        ---------
        query : torch.Tensor
            (B, L, E) where L is the target sequence length,
            B is the batch size, E is the embedding dimension.
        key : torch.Tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        value : torch.Tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        pos_embs : torch.Tensor
            bidirectional sinusoidal positional embedding tensor (1, 2*S-1, E) where S is the max length between source and target sequence lengths,
            and E is the embedding dimension.
        key_padding_mask : torch.Tensor
            (B, S) where B is the batch size, S is the source sequence
            length. If a ByteTensor is provided, the non-zero positions will
            be ignored while the position with the zero positions will be
            unchanged. If a BoolTensor is provided, the positions with the
            value of True will be ignored while the position with the value
            of False will be unchanged.
        attn_mask : torch.Tensor
            2D mask (L, S) where L is the target sequence length, S is
            the source sequence length.
            3D mask (N*num_heads, L, S) where N is the batch
            size, L is the target sequence length, S is the source sequence
            length. attn_mask ensure that position i is allowed to attend the
            unmasked positions. If a ByteTensor is provided, the non-zero
            positions are not allowed to attend while the zero positions will
            be unchanged. If a BoolTensor is provided, positions with True is
            not allowed to attend while False values will be unchanged. If a
            FloatTensor is provided, it will be added to the attention weight.
        return_attn_weights : bool
            Whether to additionally return the attention weights.

        Returns
        -------
        out : torch.Tensor
            (B, L, E) where L is the target sequence length, B is the
            batch size, E is the embedding dimension.
        attn_score : torch.Tensor
            (B, L, S) where B is the batch size, L is the target
            sequence length, S is the source sequence length.
        """

        # query, key and value are of shape batch, time, embed_dim
        bsz = query.shape[0]
        klen = key.shape[1]
        qlen = query.shape[1]

        if self._qkv_same_embed_dim:
            # self-attention
            if (query is key or torch.equal(query, key)) and (
                key is value or torch.equal(key, value)
            ):
                query, key, value = (
                    nn.functional.linear(query, self.in_proj_weight)
                    .view(bsz, -1, self.num_heads, self.head_dim * 3)
                    .chunk(3, dim=-1)
                )
            else:
                qweight, kweight, vweight = self.in_proj_weight.chunk(3, dim=0)
                query = nn.functional.linear(query, qweight).view(
                    bsz, -1, self.num_heads, self.head_dim
                )
                key = nn.functional.linear(key, kweight).view(
                    bsz, -1, self.num_heads, self.head_dim
                )
                value = nn.functional.linear(value, vweight).view(
                    bsz, -1, self.num_heads, self.head_dim
                )
        else:
            raise NotImplementedError
            query, key = (
                nn.functional.linear(query, self.qk_proj_weight)
                .view(bsz, -1, self.num_heads, self.head_dim * 2)
                .chunk(2, dim=-1)
            )
            value = nn.functional.linear(value, self.v_proj_weight).view(
                bsz, -1, self.num_heads, self.vhead_dim
            )

        if self.vbias is not None:
            value = value + self.value_bias_weight.view(
                1, 1, self.num_heads, self.vhead_dim
            )

        p_k = self.linear_pos(pos_embs).view(
            1, -1, self.num_heads, self.head_dim
        )
        # (batch, head, klen, d_k)

        q_with_bias_u = (
            query + self.pos_bias_u.view(1, 1, self.num_heads, self.head_dim)
        ).transpose(1, 2)
        # (batch, head, qlen, d_k)
        q_with_bias_v = (
            query + self.pos_bias_v.view(1, 1, self.num_heads, self.head_dim)
        ).transpose(1, 2)

        # Moved the `* self.scale` mul from after the `attn_score` sum to prior
        # to the matmul in order to lower overflow risks on fp16.
        # This change is inspired by the following paper, but no other changes
        # were ported from there so far.
        # ref: E.T.: Re-Thinking Self-Attention for Transformer Models on GPUs
        # https://asherliu.github.io/docs/sc21a.pdf

        # (batch, head, qlen, klen)
        matrix_ac = torch.matmul(
            q_with_bias_u * self.scale, key.permute(0, 2, 3, 1)
        )
        # (batch, num_heads, klen, 2*klen-1)
        matrix_bd = torch.matmul(
            q_with_bias_v * self.scale, p_k.permute(0, 2, 3, 1)
        )
        matrix_bd = self.rel_shift(matrix_bd)  # shifting trick

        # if klen != qlen:
        #   import ipdb
        #  ipdb.set_trace(

        attn_score = matrix_ac + matrix_bd  # already scaled above

        # compute attention probability
        if attn_mask is not None:
            if attn_mask.ndim == 2:
                attn_mask = attn_mask.view(1, 1, qlen, klen)
            else:
                attn_mask = attn_mask.view(-1, self.num_heads, qlen, klen)

            if attn_mask.dtype == torch.bool:
                attn_score = attn_score.masked_fill(
                    attn_mask, self.attn_fill_value
                )
            else:
                attn_score += attn_mask

        if key_padding_mask is not None:
            attn_score = attn_score.masked_fill(
                key_padding_mask.view(bsz, 1, 1, klen),
                self.attn_fill_value,
            )

        attn_score = F.softmax(attn_score, dim=-1, dtype=torch.float32)
        attn_score = self.dropout_att(attn_score)

        # it is possible for us to hit full NaN when using chunked training
        # so reapply masks, except with 0.0 instead as we are after the softmax
        # because -inf would output 0.0 regardless anyway
        if attn_mask is not None:
            if attn_mask.dtype == torch.bool:
                attn_score = attn_score.masked_fill(attn_mask, 0.0)
            else:
                # NOTE: the above fix is not implemented for this case as
                # summing the mask with NaN would still result in NaN
                pass

        if key_padding_mask is not None:
            attn_score = attn_score.masked_fill(
                key_padding_mask.view(bsz, 1, 1, klen),
                0.0,
            )

        x = torch.matmul(
            attn_score, value.transpose(1, 2)
        )  # (batch, head, time1, d_k)
        x = (
            x.transpose(1, 2)
            .contiguous()
            .view(bsz, -1, self.vhead_dim * self.num_heads)
        )  # (batch, time1, d_model)

        out = self.out_proj(x)
        if return_attn_weights:
            return out, attn_score
        return out


class MultiheadAttention(nn.Module):
    """The class is a wrapper of MultiHead Attention for torch.nn.MultiHeadAttention.

    Reference: https://pytorch.org/docs/stable/nn.html

    Arguments
    ---------
    nhead : int
        parallel attention heads.
    d_model : int
        The size of the model layers.
    dropout : float
        a Dropout layer on attn_output_weights (default: 0.0).
    bias : bool
        add bias as module parameter (default: True).
    add_bias_kv : bool
        add bias to the key and value sequences at dim=0.
    add_zero_attn : bool
        add a new batch of zeros to the key and value sequences at dim=1.
    kdim : int
        total number of features in key (default: None).
    vdim : int
        total number of features in value (default: None).

    Example
    -------
    >>> inputs = torch.rand([8, 60, 512])
    >>> net = MultiheadAttention(nhead=8, d_model=inputs.shape[-1])
    >>> outputs, attn = net(inputs, inputs, inputs)
    >>> outputs.shape
    torch.Size([8, 60, 512])
    """

    def __init__(
        self,
        nhead,
        d_model,
        dropout=0.0,
        bias=True,
        add_bias_kv=False,
        add_zero_attn=False,
        kdim=None,
        vdim=None,
    ):
        super().__init__()

        self.att = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=nhead,
            dropout=dropout,
            bias=bias,
            add_bias_kv=add_bias_kv,
            add_zero_attn=add_zero_attn,
            kdim=kdim,
            vdim=vdim,
        )

    def forward(
        self,
        query,
        key,
        value,
        attn_mask: Optional[torch.Tensor] = None,
        key_padding_mask: Optional[torch.Tensor] = None,
        return_attn_weights: bool = True,
        pos_embs: Optional[torch.Tensor] = None,
    ):
        """Compute attention.

        Arguments
        ---------
        query : torch.Tensor
            (B, L, E) where L is the target sequence length,
            B is the batch size, E is the embedding dimension.
        key : torch.Tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        value : torch.Tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        attn_mask : torch.Tensor, optional
            2D mask (L, S) where L is the target sequence length, S is
            the source sequence length.
            3D mask (N*num_heads, L, S) where N is the batch
            size, L is the target sequence length, S is the source sequence
            length. attn_mask ensure that position i is allowed to attend the
            unmasked positions. If a ByteTensor is provided, the non-zero
            positions are not allowed to attend while the zero positions will
            be unchanged. If a BoolTensor is provided, positions with True is
            not allowed to attend while False values will be unchanged. If a
            FloatTensor is provided, it will be added to the attention weight.
        key_padding_mask : torch.Tensor, optional
            (B, S) where B is the batch size, S is the source sequence
            length. If a ByteTensor is provided, the non-zero positions will
            be ignored while the position with the zero positions will be
            unchanged. If a BoolTensor is provided, the positions with the
            value of True will be ignored while the position with the value
            of False will be unchanged.
        return_attn_weights : bool, optional
            True to additionally return the attention weights, False otherwise.
        pos_embs : torch.Tensor, optional
            Positional embeddings added to the attention map of shape (L, S, E) or (L, S, 1).

        Returns
        -------
        attn_output : torch.Tensor
            (B, L, E) where L is the target sequence length, B is the
            batch size, E is the embedding dimension.
        attn_output_weights : torch.Tensor
            (B, L, S) where B is the batch size, L is the target
            sequence length, S is the source sequence length.
            This is returned only if `return_attn_weights=True` (True by default).
        """
        # give tensors of shape (time, batch, fea)
        query = query.permute(1, 0, 2)
        key = key.permute(1, 0, 2)
        value = value.permute(1, 0, 2)

        # this will be legit because of https://github.com/pytorch/pytorch/blob/5288d05cfdda85c46c4df84617fa7f37c21b10b3/torch/nn/functional.py#L4946
        # we can inject relative learnable pos embeddings directly in MHA via the attn_mask
        if pos_embs is not None:
            if attn_mask is not None:
                attn_mask += pos_embs
            else:
                attn_mask = pos_embs

        output, attention_weights = self.att(
            query,
            key,
            value,
            attn_mask=attn_mask,
            key_padding_mask=key_padding_mask,
            need_weights=return_attn_weights,
        )

        # reshape the output back to (batch, time, fea)
        output = output.permute(1, 0, 2)

        if return_attn_weights:
            return output, attention_weights

        return output


class PositionalwiseFeedForward(nn.Module):
    """The class implements the positional-wise feed forward module in
    “Attention Is All You Need”.

    Arguments
    ---------
    d_ffn: int
        Hidden layer size.
    input_shape : tuple, optional
        Expected shape of the input. Alternatively use ``input_size``.
    input_size : int, optional
        Expected size of the input. Alternatively use ``input_shape``.
    dropout: float, optional
        Dropout rate.
    activation: torch.nn.Module, optional
        activation functions to be applied (Recommendation: ReLU, GELU).

    Example
    -------
    >>> inputs = torch.rand([8, 60, 512])
    >>> net = PositionalwiseFeedForward(256, input_size=inputs.shape[-1])
    >>> outputs = net(inputs)
    >>> outputs.shape
    torch.Size([8, 60, 512])
    """

    def __init__(
        self,
        d_ffn,
        input_shape=None,
        input_size=None,
        dropout=0.0,
        activation=nn.ReLU,
    ):
        super().__init__()

        if input_shape is None and input_size is None:
            raise ValueError("Expected one of input_shape or input_size")

        if input_size is None:
            input_size = input_shape[-1]

        self.ffn = nn.Sequential(
            nn.Linear(input_size, d_ffn),
            activation(),
            nn.Dropout(dropout),
            nn.Linear(d_ffn, input_size),
        )

    def forward(self, x):
        """Applies PositionalwiseFeedForward to the input tensor x."""
        # give a tensor of shape (time, batch, fea)
        x = x.permute(1, 0, 2)
        x = self.ffn(x)

        # reshape the output back to (batch, time, fea)
        x = x.permute(1, 0, 2)

        return x
 
    
class Fastattention(nn.Module):
    """ 
    Wu et al., "Fastformer: Additive Attention Can Be All You Need"
    https://arxiv.org/pdf/2108.09084.pdf
    https://github.com/espnet/espnet/blob/master/espnet2/asr/layers/fastformer.py
    
    Arguments
    ---------
    enc_dim: int
        One of "mixing", "mixingv2", "sumonly"
        mixing = original Rogier with low rank
        mixingv2 = original rogier without low rank (S is repeated T times)
        sumonly = Shucong idea
    nhead : int
        Number of mixing heads.

    Example
    -------
    >>> x = torch.rand(2,4,8)
    >>> sum = SummaryMixing(8)
    >>> out = sum(x)
    >>> print(out)
    torch.Size([2, 4, 8])

    >>> from speechbrain.nnet.attention import Fastattention
    >>> fast = Fastattention(512, 4)
    >>> x = torch.rand(2,512,512)
    >>> out = fast(x)
    >>> out.shape
    torch.Size([2, 512, 512])
    """

    def __init__(
        self,
        enc_dim,
        nhead,
        dropout=0.0
        ):
        super(Fastattention, self).__init__()
        
        assert enc_dim % nhead == 0
        self.nhead = nhead
        self.head_dim = enc_dim // nhead
        
        self.query_proj = torch.nn.Linear(enc_dim, enc_dim)
        self.query_attn = torch.nn.Linear(enc_dim, nhead)
         
        self.key_proj = torch.nn.Linear(enc_dim, enc_dim)
        self.key_attn = torch.nn.Linear(enc_dim, nhead)
        
        self.out_proj = torch.nn.Linear(enc_dim, enc_dim)
        
        self.dropout = torch.nn.Dropout(dropout)
        
        if next(self.parameters()).dtype == torch.float16:
            self.attn_fill_value = -65000
        else:
            self.attn_fill_value = -float("inf")

        self.apply(self.init_weights)

    def init_weights(self, module):
        if isinstance(module, torch.nn.Linear):
            module.weight.data.normal_(mean=0.0, std=0.02)
        if isinstance(module, torch.nn.Linear) and module.bias is not None:
            module.bias.data.zero_()
        
    def split_n_heads(self, x):
        """Reshape and transpose to compute scores.
        Args:
            x: (batch, time, enc_dim = n_heads * head_dim)
        Returns:
            (batch, n_heads, time, head_dim)
        """

        new_x_shape = x.shape[:-1] + (
            self.nhead,
            self.head_dim,
        )
        return x.reshape(*new_x_shape).transpose(1, 2)
    
    def linear_attn(self, scores, content, padding_mask=None):
        """
        Args:
            scores (torch.Tensor): batch, time, n_heads
            content (torch.Tensor): batch, time, enc_dim
            padding_mask (Tensor): batch, time
        """        
        scores = scores.transpose(1, 2) / self.head_dim ** 0.5 # (batch, n_heads, time)
        if padding_mask is not None:
            scores = scores.masked_fill(padding_mask.unsqueeze(1), self.attn_fill_value)
            scores = torch.softmax(scores, dim=-1, dtype=torch.float32).masked_fill(padding_mask.unsqueeze(1), 0)
        else:
            scores = torch.softmax(scores, dim=-1, dtype=torch.float32)
            
        scores = scores.unsqueeze(2)  # (batch, n_heads, 1, time)
        
        summary = self.split_n_heads(content) # (batch, n_heads, time, head_dim)
        summary = torch.matmul(scores, summary) # (batch, n_heads, 1, head_dim)
        summary = self.dropout(summary)
        
        return summary # (batch, n_heads, 1, head_dim)
        
        
    
    # def forward(self, x, padding_mask=None):
    def forward(
        self,
        q,
        k, # not used
        v, # not used
        attn_mask: Optional[torch.Tensor] = None, # not used
        key_padding_mask: Optional[torch.Tensor] = None,
        return_attn_weights: Optional[bool] = True,
        pos_embs: Optional[torch.Tensor] = None,
    ):
        '''
        x : torch.Tensor
            (B, T, E) where L is the target sequence length,
            B is the batch size, E is the embedding dimension.
        padding_mask : torch.Tensor, optional
            (B, T) where B is the batch size, S is the source sequence
            length. If a ByteTensor is provided, the non-zero positions will
            be ignored while the position with the zero positions will be
            unchanged. If a BoolTensor is provided, the positions with the
            value of True will be ignored while the position with the value
            of False will be unchanged.
        '''
        x = q
        padding_mask = key_padding_mask
        B, T, E = x.shape
        
        query = self.query_proj(x) # (batch, time, enc_dim) 
        
        query_scores = self.query_attn(query) # (batch, time, n_heads)
        query_summary = self.linear_attn(query_scores, query, padding_mask) # (batch, n_heads, 1, head_dim)
        query_summary = query_summary.squeeze(2) # (batch, n_heads, head_dim)
        
        key = self.key_proj(x)
        query_summary = query_summary.view(-1, self.head_dim * self.nhead) # (batch, enc_dim)
        query_summary = query_summary.unsqueeze(1).repeat(1, T, 1) # (batch, time, enc_dim)
        key_content = key * query_summary # (batch, time, enc_dim)
        key_scores = self.key_attn(key_content) # (batch, time, n_heads)
        key_summary = self.linear_attn(key_scores, key_content, padding_mask) # (batch, n_heads, 1, head_dim)
        
        # NOTE: value = query, due to param sharing used in the paper
        value = self.split_n_heads(query) # split into (batch, n_heads, time, head_dim) 
        value = key_summary * value # (batch, n_heads, time, head_dim) 
        value = value.transpose(1,2) # (batch, time, n_heads, head_dim) 
        value = value.reshape([B, T, E]) # (batch, time, enc_dim)

        # 10/May remove self.dropout of self.out_proj(value) + query
        value = self.out_proj(value) + query
        
        return value, None


class RelPosMHAXLChunked(nn.Module):
    """ This class implements the relative multihead implementation similar to that in Transformer XL
    https://arxiv.org/pdf/1901.02860.pdf

    Arguments
    ---------
    embed_dim : int
        Size of the encoder feature vectors from which keys and values are computed.
    num_heads: int
        Number of attention heads.
    dropout : float, optional
        Dropout rate.
    vbias: bool, optional
        Whether to use bias for computing value.
    vdim: int, optional
        Size for value. Default is embed_dim (Note each head is embed_dim // num_heads).
    mask_pos_future: bool, optional
        Whether to mask future positional encodings values.
        Must be true for causal applications e.g. decoder.
    Example
    -------
    >>> inputs = torch.rand([6, 60, 512])
    >>> pos_emb = torch.rand([1, 2*60-1, 512])
    >>> net = RelPosMHAXL(num_heads=8, embed_dim=inputs.shape[-1])
    >>> outputs, attn = net(inputs, inputs, inputs, pos_emb)
    >>> outputs.shape
    torch.Size([6, 60, 512])
    """

    def __init__(
        self,
        embed_dim,
        num_heads,
        dropout=0.0,
        vbias=False,
        vdim=None,
        mask_pos_future=False,
        chunk_size=256,
    ):
        super(RelPosMHAXLChunked, self).__init__()
        self.embed_dim = embed_dim
        self.vdim = vdim if vdim is not None else embed_dim
        self._qkv_same_embed_dim = self.vdim == embed_dim
        self.mask_pos_future = mask_pos_future
        self.vbias = vbias

        self.num_heads = num_heads
        self.dropout = dropout
        self.head_dim = embed_dim // num_heads
        self.vhead_dim = self.vdim // num_heads
        self.chunk_size = chunk_size

        assert (
            self.head_dim * num_heads == self.embed_dim
        ), "embed_dim must be divisible by num_heads"
        assert (
            self.vhead_dim * num_heads == self.vdim
        ), "vdim must be divisible by num_heads"

        if self._qkv_same_embed_dim is False:
            self.qk_proj_weight = nn.Parameter(
                torch.empty(2 * embed_dim, embed_dim)
            )
            self.v_proj_weight = nn.Parameter(torch.empty(self.vdim, embed_dim))
        else:
            self.in_proj_weight = nn.Parameter(
                torch.empty(3 * embed_dim, embed_dim)
            )

        if vbias:
            self.value_bias_weight = nn.Parameter(torch.empty(self.vdim))
        else:
            self.vbias = None

        self.dropout_att = nn.Dropout(dropout)
        self.out_proj = nn.Linear(self.vdim, embed_dim)

        self.linear_pos = nn.Linear(embed_dim, embed_dim, bias=False)

        self.pos_bias_u = nn.Parameter(
            torch.empty(self.head_dim, self.num_heads)
        )
        self.pos_bias_v = nn.Parameter(
            torch.empty(self.head_dim, self.num_heads)
        )

        if next(self.parameters()).dtype == torch.float16:
            self.attn_fill_value = -65000
        else:
            self.attn_fill_value = -float("inf")

        self._reset_parameters()
        self.scale = 1 / math.sqrt(self.embed_dim)

    def _reset_parameters(self):
        if self._qkv_same_embed_dim:
            torch.nn.init.xavier_uniform_(self.in_proj_weight)
        else:
            torch.nn.init.xavier_uniform_(self.qk_proj_weight)
            torch.nn.init.xavier_uniform_(self.v_proj_weight)

        if self.vbias is not None:
            torch.nn.init.constant_(self.value_bias_weight, 0.0)

        # positional biases
        torch.nn.init.xavier_uniform_(self.pos_bias_u)
        torch.nn.init.xavier_uniform_(self.pos_bias_v)

    def rel_shift(self, x):
        """Relative shift implementation."""
        # batch, head, time1, 2*time1-1.

        b, h, qlen, pos_len = x.size()  # (b, h, t1, t2)
        # need to add a column of zeros on the left side of last dimension to perform the relative shifting
        x = torch.nn.functional.pad(x, pad=(1, 0))  # (b, h, t1, t2+1)
        x = x.view(b, h, -1, qlen)  # (b, h, t2+1, t1)
        # need to drop the first row
        x = x[:, :, 1:].view(b, h, qlen, pos_len)  # (b, h, t1, t2)

        if self.mask_pos_future:
            ones = torch.ones((x.size(2), x.size(3)), device=x.device)
            x = x * torch.tril(ones, x.size(3) - x.size(2))[None, None, :, :]

        return x[..., : pos_len // 2 + 1]

    def forward(
        self,
        query,
        key,
        value,
        pos_embs,
        key_padding_mask=None,
        attn_mask=None,
        return_attn_weights=True,
    ):
        """
        Arguments
        ----------
        query : tensor
            (B, L, E) where L is the target sequence length,
            B is the batch size, E is the embedding dimension.
        key : tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        value : tensor
            (B, S, E) where S is the source sequence length,
            B is the batch size, E is the embedding dimension.
        pos_emb : tensor
            bidirectional sinusoidal positional embedding tensor (1, 2*S-1, E) where S is the max length between source and target sequence lengths,
            and E is the embedding dimension.
        key_padding_mask : tensor
            (B, S) where B is the batch size, S is the source sequence
            length. If a ByteTensor is provided, the non-zero positions will
            be ignored while the position with the zero positions will be
            unchanged. If a BoolTensor is provided, the positions with the
            value of True will be ignored while the position with the value
            of False will be unchanged.
        attn_mask : tensor
            2D mask (L, S) where L is the target sequence length, S is
            the source sequence length.
            3D mask (N*num_heads, L, S) where N is the batch
            size, L is the target sequence length, S is the source sequence
            length. attn_mask ensure that position i is allowed to attend the
            unmasked positions. If a ByteTensor is provided, the non-zero
            positions are not allowed to attend while the zero positions will
            be unchanged. If a BoolTensor is provided, positions with True is
            not allowed to attend while False values will be unchanged. If a
            FloatTensor is provided, it will be added to the attention weight.

        Outputs
        -------
        out : tensor
            (B, L, E) where L is the target sequence length, B is the
            batch size, E is the embedding dimension.
        attn_score : tensor
            (B, L, S) where B is the batch size, L is the target
            sequence length, S is the source sequence length.
        """

        # get number of chunks
        num_chunks = key.shape[1] // self.chunk_size
        if key.shape[1] % self.chunk_size != 0:
            num_chunks += 1
        
        # ASSUMING q, k, and, v input are the same
        if (query is key or torch.equal(query, key)) and (
                key is value or torch.equal(key, value)
            ):
            # chunk input
            chunked_input = torch.chunk(query, num_chunks, dim=1)
        else:
            raise NotImplementedError

        chunk_wise_outputs =[]
        for chunk in chunked_input:
            # query, key and value are of shape batch, time, embed_dim
            bsz = chunk.shape[0]
            klen = chunk.shape[1]
            qlen = chunk.shape[1]

            query, key, value = (
                nn.functional.linear(query, self.in_proj_weight)
                .view(bsz, -1, self.num_heads, self.head_dim * 3)
                .chunk(3, dim=-1)
            )

            p_k = self.linear_pos(pos_embs).view(
                1, -1, self.num_heads, self.head_dim
            )

            # relative positional embeddings
            # (batch, head, klen, d_k)
            q_with_bias_u = (
                query + self.pos_bias_u.view(1, 1, self.num_heads, self.head_dim)
            ).transpose(1, 2)
            # (batch, head, qlen, d_k)
            q_with_bias_v = (
                query + self.pos_bias_v.view(1, 1, self.num_heads, self.head_dim)
            ).transpose(1, 2)

            # (batch, head, qlen, klen)
            matrix_ac = torch.matmul(
                q_with_bias_u * self.scale, key.permute(0, 2, 3, 1)
            )
            # (batch, num_heads, klen, 2*klen-1)
            matrix_bd = torch.matmul(
                q_with_bias_v * self.scale, p_k.permute(0, 2, 3, 1)
            )
            matrix_bd = self.rel_shift(matrix_bd)  # shifting trick

            attn_score = matrix_ac + matrix_bd  # already scaled above

            # compute attention probability
            if attn_mask is not None:
                if attn_mask.ndim == 2:
                    attn_mask = attn_mask.view(1, 1, qlen, klen)
                else:
                    attn_mask = attn_mask.view(-1, self.num_heads, qlen, klen)

                if attn_mask.dtype == torch.bool:
                    attn_score = attn_score.masked_fill(
                        attn_mask, self.attn_fill_value
                    )
                else:
                    attn_score += attn_mask

            if key_padding_mask is not None:
                attn_score = attn_score.masked_fill(
                    key_padding_mask.view(bsz, 1, 1, klen), self.attn_fill_value,
                )

            attn_score = F.softmax(attn_score, dim=-1, dtype=torch.float32)
            attn_score = self.dropout_att(attn_score)

            # it is possible for us to hit full NaN when using chunked training
            # so reapply masks, except with 0.0 instead as we are after the softmax
            # because -inf would output 0.0 regardless anyway
            if attn_mask is not None:
                if attn_mask.dtype == torch.bool:
                    attn_score = attn_score.masked_fill(attn_mask, 0.0)
                else:
                    # NOTE: the above fix is not implemented for this case as
                    # summing the mask with NaN would still result in NaN
                    pass

            if key_padding_mask is not None:
                attn_score = attn_score.masked_fill(
                    key_padding_mask.view(bsz, 1, 1, klen), 0.0,
                )

            x = torch.matmul(
                attn_score, value.transpose(1, 2)
            )  # (batch, head, time1, d_k)

            chunk_wise_outputs.append(x)

        chunk_wise_outputs = torch.cat(chunk_wise_outputs, dim=1)

        chunk_wise_outputs = (
            chunk_wise_outputs.transpose(1, 2)
            .contiguous()
            .view(bsz, -1, self.vhead_dim * self.num_heads)
        )  # (batch, time1, d_model)

        out = self.out_proj(chunk_wise_outputs)

        # will not properly return attn_score
        if return_attn_weights:
            return out, attn_score
        return out
