#!/bin/bash

# ConvFinQA Evaluator Setup Script

echo "🏦 Setting up ConvFinQA Evaluator..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python $python_version is compatible"
else
    echo "❌ Python $python_version is not compatible. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment file
if [ ! -f .env ]; then
    echo "⚙️ Creating environment file..."
    cp .env.example .env
    echo "📝 Please edit .env file with your API keys"
else
    echo "✅ Environment file already exists"
fi

# Check if data file exists
if [ ! -f data/dev_turn.json ]; then
    echo "⚠️  Data file not found. Please add your ConvFinQA dataset to data/dev_turn.json"
else
    echo "✅ Data file found"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your OpenAI API key"
echo "2. Add ConvFinQA dataset to data/dev_turn.json (if not already present)"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python src/main.py"
echo ""
echo "For more information, see README.md"