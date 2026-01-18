#!/bin/bash
# Rollback script for Care Session Service
# Usage: ./rollback.sh [revision_number]
# If no revision number is provided, rolls back to the previous deployment

set -e

NAMESPACE="${OPENSHIFT_NAMESPACE:-wailsalutem-suite}"
DEPLOYMENT="care-session-service"

echo "🔄 Rolling back deployment: $DEPLOYMENT in namespace: $NAMESPACE"

# Check if revision number is provided
if [ -z "$1" ]; then
    echo "ℹ️  No revision specified, rolling back to previous deployment..."
    oc rollout undo deployment/$DEPLOYMENT -n $NAMESPACE
else
    REVISION=$1
    echo "ℹ️  Rolling back to revision: $REVISION"
    oc rollout undo deployment/$DEPLOYMENT -n $NAMESPACE --to-revision=$REVISION
fi

# Wait for rollout to complete
echo "⏳ Waiting for rollout to complete..."
oc rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=5m

# Verify health
echo "✅ Checking service health..."
sleep 10

ROUTE_URL=$(oc get route $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.spec.host}')
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "https://$ROUTE_URL/health" || echo "000")

if [ "$HEALTH_CHECK" == "200" ]; then
    echo "✅ Rollback successful! Service is healthy."
    echo "🌐 Service URL: https://$ROUTE_URL"
else
    echo "⚠️  Warning: Health check returned status code: $HEALTH_CHECK"
    echo "Check logs: oc logs -f deployment/$DEPLOYMENT -n $NAMESPACE"
    exit 1
fi

# Show current deployment info
echo ""
echo "📊 Current deployment status:"
oc get deployment $DEPLOYMENT -n $NAMESPACE
echo ""
echo "📜 Rollout history:"
oc rollout history deployment/$DEPLOYMENT -n $NAMESPACE
