"""HTTP endpoint for contextual emergency flood-safety guidance."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import EmergencyAssistantMessageSerializer
from .services.emergency_assistant import generate_assistant_response


class EmergencyAssistantView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmergencyAssistantMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guidance = generate_assistant_response(
            serializer.validated_data["message"],
            history=serializer.validated_data["history"],
        )
        return Response(
            {
                **guidance,
                "disclaimer": (
                    "Informational guidance only. Gemini responses are AI-generated "
                    "and may be inaccurate; fallback responses are curated. Neither "
                    "is a live alert or replaces emergency services or official local instructions."
                ),
            }
        )
