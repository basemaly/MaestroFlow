FROM ghcr.io/agent-infra/sandbox:latest

# Install system dependencies for PyTorch and uv
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
ENV UV_SYSTEM_PYTHON=1
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Install PyTorch (CPU version by default for Mac/sandbox compatibility, 
# can be overridden via uv run if CUDA/MPS is needed in specific hardware environments)
RUN uv pip install --system torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

WORKDIR /workspace
