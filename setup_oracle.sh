#!/bin/bash
# One-command setup for Oracle Cloud VM (Ubuntu 20.04, x86_64)
# Usage: bash setup_oracle.sh
set -e

echo "=== Installing system packages ==="
sudo apt update
sudo apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
    libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev \
    wget libbz2-dev ffmpeg git

# Check if Python 3.11 already installed
if /usr/local/bin/python3.11 --version 2>/dev/null; then
    echo "=== Python 3.11 already installed ==="
else
    echo "=== Building Python 3.11 from source ==="
    cd /tmp
    wget -q https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
    tar xzf Python-3.11.9.tgz
    cd Python-3.11.9
    ./configure --with-openssl=/usr
    sudo make altinstall -j2
    cd ~
fi

echo "=== Setting up app ==="
cd ~/commencement_stt
rm -rf venv
/usr/local/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== Opening firewall port 3002 ==="
sudo iptables -C INPUT -p tcp --dport 3002 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT -p tcp --dport 3002 -j ACCEPT
sudo sh -c "iptables-save > /etc/iptables/rules.v4" 2>/dev/null || true

echo ""
echo "=== Setup complete! ==="
echo "To run:"
echo "  cd ~/commencement_stt"
echo "  source venv/bin/activate"
echo "  export GROQ_API_KEY='your-key'"
echo "  export OPENAI_API_KEY='your-key'"
echo "  python app.py"
