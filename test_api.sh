#!/bin/bash

# Care Session Service API Test Script
# =====================================

API_URL="https://care-session-service-wailsalutem-suite.apps.inholland-minor.openshift.eu"
TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ1VXo5LVJkTXg0MlZsRjE3aGg0ZWR0R3RFQ2E1S2FiSF90MzlsWXViVWxNIn0.eyJleHAiOjE3NjgwOTExNjEsImlhdCI6MTc2ODA4NzU2MSwianRpIjoiNjc4MmQzZmYtZGIxZC00YzU3LWJjNjEtYmFjYTkzNWZiYWJlIiwiaXNzIjoiaHR0cHM6Ly9rZXljbG9hay13YWlsc2FsdXRlbS1zdWl0ZS5hcHBzLmluaG9sbGFuZC1taW5vci5vcGVuc2hpZnQuZXUvcmVhbG1zL3dhaWxzYWx1dGVtIiwiYXVkIjoiYWNjb3VudCIsInN1YiI6IjU4MjBkYzc5LTI2ZTUtNGZkNy1iYTIyLTdhNzkzNzA0M2Q2NSIsInR5cCI6IkJlYXJlciIsImF6cCI6IndhaWxzYWx1dGVtLWFwaSIsInNlc3Npb25fc3RhdGUiOiJiY2Y5ZmZlNS0yM2VhLTRhZDctYWI0My05ZjUzMWQ0ZjlkODQiLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbImh0dHA6Ly9sb2NhbGhvc3Q6MzAwMCJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy13YWlsc2FsdXRlbSIsIm9mZmxpbmVfYWNjZXNzIiwidW1hX2F1dGhvcml6YXRpb24iLCJPUkdfQURNSU4iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6ImVtYWlsIHByb2ZpbGUiLCJzaWQiOiJiY2Y5ZmZlNS0yM2VhLTRhZDctYWI0My05ZjUzMWQ0ZjlkODQiLCJvcmdhbml6YXRpb25JRCI6IjMxNTI5OGJmLTAwNjktNGI4MS05NDY5LWM1OTg2NzBhMmFmMiIsIm9yZ1NjaGVtYU5hbWUiOiJvcmdfbGlmZWNhcmVfaGVhbHRoY2FyZV8zMTUyOThiZiIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwibmFtZSI6Ik11aGFtbWFkIEZhaXphbiIsInByZWZlcnJlZF91c2VybmFtZSI6ImZhaXplZXkiLCJnaXZlbl9uYW1lIjoiTXVoYW1tYWQiLCJmYW1pbHlfbmFtZSI6IkZhaXphbiIsImVtYWlsIjoiZmFpemFuQGdtYWlsLmNvbSJ9.YFuPtMa4DajlEAsDtnyUuSWBp2CF6jG1Xe4FqLylcToANbahd2HUglZNjQUFXYxgqULEt-DlwqTUEB5t-ZMO0P_5C3tb-HwiNsT0vS4DNIzUL1N4EBJZ46fE9bIv73ZZc9606tG1jLFVurz4UczZVZabmvrzEUwxVItgWVwSKQKwqYVWi7ke01-mOb6hEtyP-WGABRyTkvESDxqNAdUaEtPMOqj66stFLcGaVHY4g6GGnzotLPYatxubwLDWZDRiVkARMEnvDKRFdHMmFVRiVSA_Rg5I6U5L4VGPBzkCOqO3mrgGcTGSgqZh8-HzbjgI7eiCQZzuMxTaUauudUboIw"

echo "==================================="
echo "Care Session Service API Tests"
echo "==================================="
echo ""

# Test 1: Health Check
echo "1. Testing Health Endpoint..."
curl -s -X GET "$API_URL/health" \
  -H "Content-Type: application/json" | jq .
echo ""

# Test 2: List Care Sessions
echo "2. Testing List Care Sessions..."
curl -s -X GET "$API_URL/care-sessions/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo ""

# Test 3: Create a Care Session
echo "3. Testing Create Care Session..."
curl -s -X POST "$API_URL/care-sessions/create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tag_id": "NFC123456",
    "session_id": "session-'$(date +%s)'"
  }' | jq .
echo ""

# Test 4: Get Reports
echo "4. Testing Reports Endpoint..."
curl -s -X GET "$API_URL/reports/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo ""

# Test 5: Get Feedback
echo "5. Testing Feedback Endpoint..."
curl -s -X GET "$API_URL/feedback/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo ""

echo "==================================="
echo "Tests Complete!"
echo "===================================" 
