# 基于逐骨变分自编码器与潜空间流匹配扩散变换器的蒙皮权重生成方法

## 技术交底书

---

## 一、技术领域

本发明涉及计算机图形学中的角色蒙皮技术领域，具体涉及一种基于深度生成模型的自动蒙皮权重预测方法。该方法结合了逐骨变分自编码器（Per-Bone Shape VAE）和潜空间流匹配扩散变换器（Per-Bone Shape DiT），实现了从三维网格和骨骼信息到逐顶点蒙皮权重的高质量自动生成。

---

## 二、背景技术

### 2.1 蒙皮权重的定义与重要性

在三维角色动画中，蒙皮权重（Skinning Weights）定义了网格上每个顶点跟随各个骨骼运动的程度。对于一个拥有 N 个顶点和 M 根骨骼的角色网格，蒙皮权重矩阵 W ∈ R^{N×M} 的每一行是一个概率分布（各元素非负且行和为 1），表示该顶点受各骨骼的影响权重。

高质量蒙皮权重的手工制作是游戏和影视制作中最耗时的环节之一。一个典型的角色模型拥有 5,000 至 50,000 个顶点和 50 至 350 根骨骼，技术美术师通常需要数小时甚至数天来逐顶点调整权重。因此，自动蒙皮权重预测具有重大的工业价值。

### 2.2 现有技术的不足

现有的自动蒙皮方法主要包括以下几类：

**基于几何的方法**（如热扩散方法 Heat Diffusion）：通过求解拉普拉斯方程计算顶点到骨骼的权重。这类方法不需要训练数据，但生成的权重质量有限，无法捕捉复杂的蒙皮模式（如服装跟随、肌肉变形等）。

**基于判别式模型的方法**：使用图神经网络或 Transformer 编码器直接回归权重矩阵。这类方法能学习训练数据中的蒙皮模式，但输出是确定性的，无法处理蒙皮权重固有的多义性（同一几何形状可能对应多种合理的蒙皮方案），且在遇到训练分布外的模型时泛化能力受限。

**基于生成模型的方法**：现有的生成式蒙皮方法大多直接在权重空间或全网格空间建模，导致模型需要处理极高维度的输出空间（N×M 可达数百万维），训练效率低且生成质量不稳定。

### 2.3 本发明要解决的技术问题

本发明旨在解决以下技术问题：

1. 如何将高维蒙皮权重空间有效压缩到低维潜空间，以支持高效的生成建模；
2. 如何利用扩散模型在潜空间中进行条件生成，充分利用网格几何、骨骼结构和全局形状信息；
3. 如何实现逐骨粒度的建模，使模型能够独立处理每根骨骼的蒙皮域，并适应不同骨骼数量的角色。

---

## 三、发明内容

### 3.1 技术方案概述

本发明提出了一种两阶段的蒙皮权重生成方法：

**第一阶段（潜空间编码）**：训练一个逐骨变分自编码器（Per-Bone Shape VAE），将每根骨骼的蒙皮表面（由顶点位置、法线和权重构成的点云）编码为一组连续高斯潜变量。每根骨骼的蒙皮域被压缩为 T 个潜向量（例如 T=8），每个潜向量的维度为 E（例如 E=1024）。

**第二阶段（潜空间生成）**：训练一个流匹配扩散变换器（Per-Bone Shape DiT），在 VAE 的潜空间中进行条件生成。DiT 以顶点特征、骨骼特征和全局形状特征为条件，通过整流流（Rectified Flow）训练范式生成所有骨骼的潜变量，再由冻结的 VAE 解码器还原为蒙皮权重。

### 3.2 系统整体架构

整体系统的数据流如下：

```
输入: 三维网格 (顶点、法线、拓扑) + 骨骼层级 (关节位置、父子关系)
                          ↓
                   特征提取模块
            ┌──────────┼──────────┐
        顶点特征    骨骼特征    形状特征
       [B,N,704]  [B,M,256]  [B,S,768]
            └──────────┼──────────┘
                       ↓
              Per-Bone Shape DiT
         (流匹配扩散变换器, 24层)
                       ↓
            生成潜变量 z [B, M×8, 1024]
                       ↓
              Per-Bone Shape VAE
               (冻结解码器)
                       ↓
            蒙皮权重 W [N, M]
```

---

## 四、具体实施方式

### 4.1 逐骨变分自编码器（Per-Bone Shape VAE）

#### 4.1.1 设计动机

传统的全网格 VAE 需要同时编码所有顶点和所有骨骼的交互信息，潜空间维度随骨骼数量线性增长，导致训练困难。本发明的关键创新在于**将蒙皮权重建模分解为逐骨独立的编码-解码问题**：每根骨骼拥有独立的蒙皮域（影响范围内的点云及其权重），可以独立编码和解码。

这种分解的优势包括：
- 潜空间维度与单骨复杂度相关，而非总骨骼数，大幅降低了建模难度；
- 模型天然支持不同骨骼数量的角色（从 30 根到 350 根）；
- 骨骼间的关联关系交由下游的 DiT 模型建模，实现了关注点分离。

#### 4.1.2 编码器架构

编码器采用 PointFieldEncoder 架构，将每根骨骼的蒙皮表面编码为连续高斯分布的参数。

**输入表示**：对于第 m 根骨骼，输入为该骨骼影响范围内的点云表面 S_m ∈ R^{P×7}，其中 P 为采样点数量，7 个通道分别为三维坐标 (x,y,z)、表面法线 (n_x, n_y, n_z) 和蒙皮权重值 w。

**傅里叶位置编码**：首先对三维坐标应用傅里叶位置编码：

```python
class FourierEmbedder:
    """将 3D 坐标映射到高频傅里叶特征空间"""
    def __init__(self, num_freqs=8, include_pi=False):
        # 生成频率带: [2^0, 2^1, ..., 2^(num_freqs-1)] × π
        freq_bands = 2.0 ** torch.linspace(0, num_freqs - 1, num_freqs)
        if include_pi:
            freq_bands = freq_bands * math.pi
        self.register_buffer("freq_bands", freq_bands)

    def forward(self, coords):  # coords: [B, P, 3]
        # 对每个坐标维度应用 sin 和 cos: 输出维度 = 3 × num_freqs × 2
        proj = coords[..., None] * self.freq_bands  # [B, P, 3, num_freqs]
        return torch.cat([proj.sin(), proj.cos()], dim=-1).flatten(-2)
```

傅里叶编码将低维坐标映射到高维频率空间，使网络能够捕捉蒙皮权重的高频空间变化模式。

**交叉注意力编码**：编码后的点云特征通过交叉注意力机制压缩到固定数量的可学习潜向量查询中：

```python
class PointFieldEncoder(nn.Module):
    def __init__(self, fourier_embedder, num_latents, point_feats, width, heads, layers, ...):
        self.query_proj = nn.Parameter(torch.randn(num_latents, width))  # T 个可学习查询
        self.cross_attn = CrossAttention(width, heads)  # 查询 → 点云特征
        self.self_attn = Transformer(width, layers, heads)  # 自注意力精炼

    def forward(self, pc, feats):
        # pc: [B, P, 3] 坐标, feats: [B, P, 4] 特征(法线+权重)
        fourier = self.fourier_embedder(pc)  # [B, P, fourier_dim]
        x = torch.cat([fourier, feats], dim=-1)  # [B, P, fourier_dim + 4]
        x = self.input_proj(x)  # [B, P, width]

        queries = self.query_proj.unsqueeze(0).expand(B, -1, -1)  # [B, T, width]
        latent = self.cross_attn(queries, x)  # [B, T, width], T << P
        latent = self.self_attn(latent)  # [B, T, width]
        return latent
```

这一步将变长的点云（P 点，可从数百到数万）压缩为固定 T 个（例如 8 个）潜向量，每个维度为 width（例如 1024）。

**VAE 瓶颈层**：编码器输出通过两个线性投影分别得到均值 μ 和对数方差 log σ²：

```python
# VAE 瓶颈层: 将编码器输出分裂为 mu 和 log_var
self.to_mu = nn.Linear(width, embed_dim)      # width → embed_dim
self.to_logvar = nn.Linear(width, embed_dim)  # width → embed_dim

def encode(self, surface):  # surface: [B, P, 7]
    pc = surface[:, :, :3]        # 坐标
    feats = surface[:, :, 3:]     # 法线 + 权重
    hidden = self.encoder(pc, feats)  # [B, T, width]
    mu = self.to_mu(hidden)           # [B, T, E]
    logvar = self.to_logvar(hidden)   # [B, T, E]
    return mu, logvar
```

#### 4.1.3 重参数化与 KL 散度

在训练阶段，采用重参数化技巧从后验分布中采样：

```python
@staticmethod
def reparameterize(mu, logvar):
    """z ~ N(mu, sigma^2), 采用重参数化技巧保证梯度可回传"""
    std = (0.5 * logvar).exp()       # σ = exp(0.5 × log σ²)
    eps = torch.randn_like(std)      # ε ~ N(0, I)
    return mu + eps * std            # z = μ + ε × σ
```

在推理阶段，直接使用均值 μ 作为潜变量，确保输出的确定性：

```python
if self.training:
    z = self.reparameterize(mu, logvar)  # 训练: 随机采样
else:
    z = mu  # 推理: 使用均值
```

KL 散度计算使用标准高斯先验 N(0, I)：

```python
@staticmethod
def kl_divergence(mu, logvar):
    """KL(q(z|x) || N(0, I)), 在所有维度 (B, T, E) 上取平均"""
    kl_per_element = -0.5 * (1.0 + logvar - mu.pow(2) - logvar.exp())
    return kl_per_element.mean()
```

为防止训练早期编码器坍塌（encoder collapse），KL 损失采用 Free-Bits 稳定化策略：

```python
class LatentKLLoss(BaseLoss):
    """带 Free-Bits 稳定化的 VAE KL 损失"""
    def __init__(self, free_bits=0.0, hard_clamp=None):
        self.free_bits = free_bits    # 低于此阈值的 KL 被归零
        self.hard_clamp = hard_clamp  # 最大 KL 值，防止梯度爆炸

    def forward(self, context):
        kl = context.extras["kl"]     # 从 VAE 前向传播获取
        if self.free_bits > 0:
            kl = torch.clamp(kl - self.free_bits, min=0.0)
        if self.hard_clamp is not None:
            kl = torch.clamp(kl, max=self.hard_clamp)
        return kl
```

#### 4.1.4 解码器架构

解码器由两部分组成：

**潜变量变换器**：首先将潜变量通过线性层映射回 Transformer 的隐藏维度，再经过多层自注意力进行特征精炼：

```python
def decode(self, z, latent_mask=None):
    """将潜变量解码为隐藏表示"""
    hidden = self.post_latent(z)  # [B, T, E] → [B, T, width]
    return self.transformer(hidden, key_padding_mask=latent_mask)  # 16 层自注意力
```

**交叉注意力几何解码器**：最终通过交叉注意力机制，将查询点的空间坐标与解码后的潜向量进行交叉注意力计算，输出每个查询点对该骨骼的蒙皮权重：

```python
class CrossAttentionDecoder(nn.Module):
    """交叉注意力几何解码器: 查询点 → 潜变量 → 蒙皮权重"""
    def forward(self, queries, latents, latent_mask=None):
        # queries: [B, Q, 3] 查询点坐标
        # latents: [B, T, width] 解码后的潜向量
        q_fourier = self.fourier_embedder(queries)  # 傅里叶编码
        q_proj = self.query_proj(q_fourier)          # 线性投影

        # 交叉注意力: Q=查询点, KV=潜向量
        output = self.cross_attn(q_proj, latents, key_padding_mask=latent_mask)
        return self.output_proj(output)  # [B, Q, 1] 蒙皮权重
```

解码器输出经过 Sigmoid 激活后得到 [0,1] 范围的蒙皮权重值。

#### 4.1.5 形状特征融合

对于可选的全局形状特征（来自外部预训练的形状编码器），VAE 通过双线性插值将其对齐到潜变量的尺寸后拼接：

```python
def _project_shape_tokens(self, shape_tokens):
    """将外部形状特征投影并对齐到潜变量空间"""
    projected = self.shape_feature_proj(shape_tokens)  # [S, D] → [S, E]
    # 双线性插值对齐到 (T, E) 尺寸
    aligned = F.interpolate(
        projected.unsqueeze(0).unsqueeze(0),
        size=(self.num_latents, self.embed_dim),
        mode="bilinear", align_corners=False,
    )
    return aligned.squeeze(0).squeeze(0)  # [T, E]

def _concat_shape_latents(self, latent_codes, shape_features):
    """将形状特征拼接到潜变量序列末尾"""
    shape_tokens = self._project_shape_tokens(shape_features)
    shape_tokens = shape_tokens.unsqueeze(0).expand(B, -1, -1)  # [B, T, E]
    return torch.cat([latent_codes, shape_tokens], dim=1)  # [B, 2T, E]
```

#### 4.1.6 VAE 训练目标

VAE 的总训练损失由重建损失和 KL 正则化组成：

```
L_VAE = L_recon + β × L_KL
```

其中重建损失采用 Clamped MAPE（截断平均绝对百分比误差），β 为 KL 权重（典型值为 1e-3），KL 损失带有 Free-Bits 稳定化。

训练配置（来自 YAML 配置文件）：

```yaml
model:
  skinning_encoder:
    target: src.custom_models.per_bone_shape_vae.PerBoneShapeVAE
    params:
      num_latents: 8           # 每骨 8 个潜向量
      embed_dim: 1024          # 潜变量维度
      width: 1024              # Transformer 隐藏维度
      heads: 16                # 注意力头数
      num_encoder_layers: 8    # 编码器层数
      num_decoder_layers: 16   # 解码器层数
      num_freqs: 8             # 傅里叶频率数

loss:
  components:
    - target: src.losses.components.clamped_mape_loss.ClampedMAPELoss
      weight: 1.0
    - target: src.losses.components.latent_kl_loss.LatentKLLoss
      weight: 0.001
      params:
        free_bits: 0.0
```

---

### 4.2 逐骨潜空间流匹配扩散变换器（Per-Bone Shape DiT）

#### 4.2.1 设计动机

VAE 提供了一个结构化的潜空间：每根骨骼被表示为 8 个 1024 维的潜向量。然而，仅靠 VAE 的解码器无法生成新的蒙皮权重，因为它需要先有潜变量作为输入。DiT 的作用是学习在这个潜空间中的条件分布，给定网格几何和骨骼信息，生成合理的潜变量序列。

选择流匹配（Flow Matching）而非传统的 DDPM 扩散作为训练范式，基于以下考虑：
- 流匹配使用直线插值路径，采样效率更高（通常 50 步即可达到高质量）；
- 速度场（velocity field）的回归目标比噪声预测更稳定；
- 与 SD3/Flux 等最新图像生成模型的架构兼容，可复用成熟的工程实践。

#### 4.2.2 单流拼接架构

DiT 采用 SD3/Flux 风格的单流拼接架构，将条件 token 和目标潜变量 token 拼接为一个统一序列，通过联合自注意力处理：

```
序列布局:
[顶点条件(256 tokens) | 形状条件(S tokens) | 骨骼条件(350 tokens) | 骨骼潜变量(350×8=2800 tokens)]
```

这种设计的关键优势在于：
- 条件 token 和目标 token 共享同一个注意力场，实现了隐式的交叉注意力；
- 条件 token 不加噪，保持了干净的条件信号；
- 仅对潜变量部分计算速度场预测和损失。

#### 4.2.3 条件构建模块

**顶点特征压缩**：原始顶点特征维度为 [B, N_v, 704]，顶点数 N_v 可达数万。采用 Perceiver 交叉注意力压缩器将变长顶点序列压缩为固定 256 个 token：

```python
class PerceiverCompressor(nn.Module):
    """将变长顶点特征压缩为固定数量的 token"""
    def __init__(self, input_dim, output_dim, num_compressed_tokens=256,
                 num_heads=8, num_layers=2):
        self.queries = nn.Parameter(torch.randn(num_compressed_tokens, output_dim))
        self.input_proj = nn.Linear(input_dim, output_dim)
        self.layers = nn.ModuleList([
            PerceiverLayer(output_dim, num_heads) for _ in range(num_layers)
        ])

    def forward(self, x):  # x: [N_v, input_dim], 变长
        x = self.input_proj(x)  # [N_v, output_dim]
        q = self.queries  # [256, output_dim]
        for layer in self.layers:
            # 交叉注意力: Q=可学习查询, KV=顶点特征
            q = q + layer.cross_attn(q, x)
            q = q + layer.ffn(layer.norm(q))
        return self.final_norm(q)  # [256, output_dim]
```

Perceiver 压缩器通过 2 层迭代交叉注意力，将可能多达 60,000+ 个顶点的特征压缩为 256 个固定维度的表示，实现了 O(N_v) 到 O(1) 的序列长度缩减。

**骨骼特征编码**：骨骼特征由预计算的骨骼嵌入和正弦位置编码组成：

```python
# 骨骼位置编码: 6D 关节坐标 → 高维嵌入
self.bone_pos_embed = PointEmbed(hidden_dim=192, dim=256)

# 骨骼特征投影: 拼接特征 + 位置编码后映射到隐藏维度
self.bone_proj = nn.Sequential(
    nn.LayerNorm(bone_feat_dim + bone_pos_embed_dim),  # 256 + 256 = 512
    nn.Linear(512, hidden_size),
    nn.GELU(),
    nn.Linear(hidden_size, hidden_size),
)
```

其中 PointEmbed 使用正弦波编码将 6D 关节坐标（起点 xyz + 终点 xyz）映射到 256 维空间，为模型提供精确的骨骼空间位置信息。

**形状特征投影**：全局形状特征通过两层 MLP 映射到 Transformer 隐藏维度：

```python
self.shape_proj = nn.Sequential(
    nn.LayerNorm(shape_feature_dim),  # 768
    nn.Linear(768, hidden_size),
    nn.GELU(),
    nn.Linear(hidden_size, hidden_size),
)
```

#### 4.2.4 潜变量输入处理

噪声潜变量通过线性投影和可学习位置嵌入进入 Transformer：

```python
self.latent_in = nn.Linear(latent_dim, hidden_size)  # 1024 → 1024
self.latent_pos_embed = nn.Embedding(max_bones * num_latents_per_bone, hidden_size)
# max_bones × num_latents_per_bone = 350 × 8 = 2800 个独立位置

def forward(self, x, t, ...):
    pos_ids = torch.arange(self.max_latent_tokens, device=x.device)
    lat = self.latent_in(x) + self.latent_pos_embed(pos_ids)[None]  # [B, 2800, H]
```

每个骨骼-潜变量位置拥有独立的可学习嵌入，使模型能够区分不同骨骼以及同一骨骼内的不同潜变量位置。

#### 4.2.5 时间步调制

采用 AdaLN（自适应层归一化）进行时间步调制，遵循 SD3/Flux 的设计：

```python
# 时间步嵌入: σ → 正弦编码 → MLP
self.time_in = MLPEmbedder(in_dim=256, hidden_dim=hidden_size)

def forward(self, x, t, ...):
    # t: [B], σ ∈ [0, 1]
    t_emb = timestep_embedding(t, 256, time_factor=1000.0)  # 正弦编码
    vec = self.time_in(t_emb)  # [B, hidden_size]
```

时间步向量 `vec` 通过每个 Transformer 块中的 Modulation 模块生成 scale、shift、gate 参数，调制归一化后的特征：

```python
class SingleStreamBlock(nn.Module):
    """带 AdaLN 时间步调制的单流 Transformer 块"""
    def forward(self, x, vec):
        mod, _ = self.modulation(vec)  # 生成 scale, shift, gate
        x_mod = (1 + mod.scale) * self.pre_norm(x) + mod.shift  # AdaLN

        qkv, mlp = torch.split(self.linear1(x_mod), [3*H, mlp_dim], dim=-1)
        q, k, v = rearrange(qkv, "B L (K H D) -> K B H L D", K=3, H=num_heads)
        q, k = self.qk_norm(q, k, v)  # QK 归一化

        attn = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_bias)
        attn = rearrange(attn, "B H L D -> B L (H D)")

        output = self.linear2(torch.cat([attn, gelu(mlp)], dim=2))
        return x + mod.gate * output  # 门控残差
```

#### 4.2.6 注意力掩码机制

由于不同样本的有效骨骼数量不同，需要对填充位置进行掩码。本发明构建了一个二维加性注意力偏置矩阵：

```python
@staticmethod
def _build_attn_bias(mask):
    """从布尔掩码构建加性注意力偏置
    
    Args:
        mask: [B, S], True=有效 token, False=填充
    Returns:
        [B, 1, S, S] 浮点张量: 有效对为 0, 填充对为 -inf
    """
    if mask.all():
        return None  # 无填充时跳过，节省计算
    # 二维掩码: attn[i,j] 有效当且仅当 mask[i] AND mask[j]
    mask_2d = mask.unsqueeze(1) & mask.unsqueeze(2)  # [B, S, S]
    bias = torch.zeros_like(mask_2d, dtype=torch.float32)
    bias.masked_fill_(~mask_2d, float("-inf"))
    return bias.unsqueeze(1)  # [B, 1, S, S]
```

这种设计确保了填充位置既不作为查询（不会注意到任何 token）也不作为键（不会被任何 token 注意到），避免了填充信息泄漏。

#### 4.2.7 流匹配训练

训练过程遵循整流流（Rectified Flow）范式：

```python
def compute_loss(self, batch, ...):
    # 1. 冻结的 VAE 编码 GT 表面 → 干净潜变量 z_1
    z_1 = self._encode_with_vae(batch)  # [B, M×8, 1024]

    # 2. 潜空间归一化 (使分布接近 N(0,1))
    z_1 = (z_1 - self.latent_shift) * self.latent_scale

    # 3. 采样 σ ~ LogitNormal(mean, std) 和噪声 ε ~ N(0,I)
    sigma = self._sample_sigma(batch_size)  # σ ∈ (0, 1)
    noise = torch.randn_like(z_1)           # ε ~ N(0, I)

    # 4. 构造噪声潜变量: z_σ = (1-σ)·z_1 + σ·ε
    sigma_bc = sigma[:, None, None]
    z_sigma = (1 - sigma_bc) * z_1 + sigma_bc * noise

    # 5. 速度目标: v = ε - z_1 (diffusers 约定)
    v_target = noise - z_1

    # 6. DiT 预测速度场
    v_pred = self.denoiser(
        x=z_sigma, t=sigma,
        vertex_features=vertex_features,
        bone_features=bone_features,
        bone_pos=bone_pos,
        bone_mask=bone_mask,
        shape_features=shape_features,
        vertex_pos_norm=vertex_pos_norm,
    )

    # 7. 掩码 MSE 损失 (仅计算有效骨骼位置)
    latent_mask = bone_mask.unsqueeze(-1).expand(-1, -1, num_latents)
    latent_mask = latent_mask.reshape(B, -1)  # [B, M×8]
    diff_sq = (v_pred - v_target).pow(2).mean(dim=-1)  # [B, M×8]
    loss = (diff_sq * latent_mask).sum() / (latent_mask.sum() * latent_dim)
```

其中 σ 的采样使用 LogitNormal 分布（均值 0.0，标准差 1.0），这是 SD3 论文中推荐的采样策略，能够在中等噪声水平提供更密集的训练信号。

#### 4.2.8 潜空间归一化

为了使 VAE 潜空间的分布与标准高斯先验对齐（流匹配假设起点为标准高斯噪声），本发明引入了潜空间归一化：

```python
# 归一化: z_norm = (z - shift) × scale
# 通过 1000 个训练样本统计得到: mean ≈ 0, std ≈ 1.13
latent_shift: 0.0      # 均值偏移
latent_scale: 0.8853   # 1/std ≈ 1/1.13 ≈ 0.8853

# 训练时归一化
if self.latent_scale != 1.0 or self.latent_shift != 0.0:
    z_1 = (z_1 - self.latent_shift) * self.latent_scale

# 推理时反归一化
z = z / self.latent_scale + self.latent_shift
```

#### 4.2.9 推理流程

推理采用 Euler ODE 积分，使用 diffusers 库的 FlowMatchEulerDiscreteScheduler：

```python
def _predict_batch_flow(self, batch, ...):
    # 1. 从纯噪声开始 (归一化潜空间)
    z = torch.randn(B, M*num_latents, latent_dim)

    # 2. Euler ODE 积分: 从 σ=1 (噪声) 到 σ=0 (干净数据)
    scheduler = FlowMatchEulerDiscreteScheduler(num_train_timesteps=1000, shift=1.0)
    scheduler.set_timesteps(num_inference_steps=50)

    for t in scheduler.timesteps:
        sigma = (t / 1000).expand(B)
        v_pred = denoiser(x=z, t=sigma, ...)
        z = scheduler.step(v_pred, t, z)[0]  # z_next = z + (σ_next - σ) × v

    # 3. 反归一化回 VAE 原始尺度
    z = z / self.latent_scale + self.latent_shift

    # 4. VAE 解码: 潜变量 → 蒙皮权重
    z = z.reshape(B, M, num_latents, latent_dim)
    for i in range(B):
        n_bones = bone_mask[i].sum()
        z_i = z[i, :n_bones]  # [n_bones, 8, 1024]
        # 分块解码防止 OOM
        for start in range(0, n_bones, bone_chunk):
            end = min(start + bone_chunk, n_bones)
            pred = self.vae.geo_decoder(queries, z_i[start:end])
            pred = torch.sigmoid(pred)
        weights_list.append(pred)  # [N, n_bones]
```

#### 4.2.10 分块 VAE 编解码

由于单个样本的骨骼数可达 350，一次性编码或解码所有骨骼会导致 GPU 内存溢出。本发明采用分块处理策略：

```python
# 编码时: 按 vae_encode_chunk (默认 32) 根骨骼分块
vae_encode_chunk = 32
mu_chunks = []
for start in range(0, n_bones, vae_encode_chunk):
    end = min(start + vae_encode_chunk, n_bones)
    mu_c, _ = self.vae.encode(surface_i[start:end])
    mu_chunks.append(mu_c)
mu = torch.cat(mu_chunks, dim=0)

# 解码时: 按 bone_chunk (默认 4) 根骨骼分块
bone_chunk = 4
pred_chunks = []
for b_start in range(0, n_bones, bone_chunk):
    b_end = min(b_start + bone_chunk, n_bones)
    out = self.vae.geo_decoder(queries[b_start:b_end], decoded[b_start:b_end])
    pred_chunks.append(out)
pred = torch.cat(pred_chunks, dim=0)
```

---

### 4.3 训练流程

整个系统的训练分为两个阶段：

**第一阶段：VAE 训练**
- 目标：学习逐骨蒙皮域的压缩表示
- 损失：Clamped MAPE 重建损失 + KL 散度正则化（权重 1e-3）
- 训练步数：100,000 步
- 批次策略：动态批次，最大 token 预算 160 万
- 精度：BF16 混合精度
- 训练完成后冻结 VAE 参数

**第二阶段：DiT 训练**
- 目标：在 VAE 潜空间中学习条件生成
- 损失：掩码 MSE 速度场回归损失
- 训练步数：200,000 步
- σ 采样：LogitNormal(mean=0.0, std=1.0)
- 潜空间归一化：scale=0.8853, shift=0.0
- 推理步数：50 步 Euler ODE 积分
- 精度：BF16 混合精度

---

## 五、发明的有益效果

1. **高效的潜空间建模**：通过逐骨分解将 N×M 维的权重空间压缩为 M×8×1024 维的潜空间，大幅降低了生成建模的难度。

2. **条件生成能力**：DiT 能够利用丰富的条件信息（顶点几何、骨骼结构、全局形状）进行条件生成，生成结果与输入角色高度一致。

3. **可扩展性**：逐骨设计使模型天然支持不同骨骼数量（30-350）的角色，无需针对特定骨架结构重新训练。

4. **两阶段解耦**：VAE 和 DiT 的解耦训练降低了整体训练难度，且各阶段可独立迭代优化。

5. **高效推理**：流匹配范式仅需 50 步即可生成高质量蒙皮权重，结合分块编解码策略，可在单 GPU 上处理大型角色模型。

6. **多义性建模**：与判别式方法不同，生成模型能够对蒙皮权重的不确定性进行建模，对同一输入可生成多种合理的蒙皮方案。

---

## 六、权利要求要点

1. 一种逐骨变分自编码器，将每根骨骼的蒙皮表面独立编码为连续高斯潜变量，其中编码器使用傅里叶位置编码和交叉注意力将变长点云压缩为固定数量的潜向量。

2. 一种基于流匹配的扩散变换器，在所述变分自编码器的潜空间中进行条件生成，其中条件 token（顶点、骨骼、形状）与噪声潜变量 token 拼接为统一序列通过自注意力联合处理。

3. 一种 Perceiver 交叉注意力压缩器，将变长顶点特征序列（可达数万个顶点）压缩为固定数量的条件 token。

4. 所述扩散变换器采用 AdaLN 时间步调制机制和二维加性注意力掩码处理变长骨骼序列。

5. 一种潜空间归一化方法，通过预计算的统计量将 VAE 潜空间分布对齐到标准高斯分布，提升流匹配训练的稳定性。

6. 一种分块编解码策略，按骨骼分块进行 VAE 编码和解码，支持骨骼数达 350 的大型角色模型在单 GPU 上推理。

---

## 附录：关键配置参数

| 参数 | VAE | DiT |
|------|-----|-----|
| 隐藏维度 | 1024 | 1024 |
| 注意力头数 | 16 | 16 |
| Transformer 层数 | 编码器 8 + 解码器 16 | 24 |
| 每骨潜向量数 | 8 | 8 |
| 潜向量维度 | 1024 | 1024 |
| 最大骨骼数 | — | 350 |
| 顶点压缩 token 数 | — | 256 |
| 训练步数 | 100,000 | 200,000 |
| 学习率 | 1e-4 | 1e-4 |
| 混合精度 | BF16 | BF16 |
| 推理步数 | — | 50 |
