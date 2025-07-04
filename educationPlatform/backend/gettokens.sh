#!/bin/bash

# Bash script to get Azure tokens and run pregrade.py
echo "🔐 Getting Azure Cosmos DB access token..."

# Get Cosmos DB access token
COSMOS_ACCESS_TOKEN=$(az account get-access-token --resource https://cosmos.azure.com --query accessToken --output tsv)
if [ $? -ne 0 ]; then
    echo "❌ Failed to get Cosmos DB access token"
    exit 1
fi

export COSMOS_ACCESS_TOKEN
echo "✅ Cosmos DB token set successfully"

echo "🔐 Getting Azure AI access token..."

# Get Azure AI access token
AZURE_AI_ACCESS_TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken --output tsv)
if [ $? -ne 0 ]; then
    echo "❌ Failed to get Azure AI access token"
    exit 1
fi

export AZURE_AI_ACCESS_TOKEN
echo "✅ Azure AI token set successfully"

echo "🚀 Starting Python application..."

# Run the Python application
python pregrade.py

if [ $? -ne 0 ]; then
    echo "❌ Python application failed"
    exit 1
fi

echo "✅ Application completed successfully"
