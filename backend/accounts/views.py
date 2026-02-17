import csv
import secrets
from io import TextIOWrapper

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, EmailVerificationToken, PasswordResetToken
from .serializers import (
    SignupSerializer, VerifyEmailSerializer, UserMeSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer
)
from .permissions import IsAdmin
from .tokens import new_token


def send_verification_email(user: User):
    token = new_token(16)
    EmailVerificationToken.objects.create(user=user, token=token)

    verify_url = f"{settings.FRONTEND_BASE_URL}/verify.html?token={token}"
    subject = "Verify your Codavatar InternTrack account"
    message = f"Hello {user.full_name},\n\nPlease verify your account:\n{verify_url}\n\n- Codavatar Tech"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def send_reset_email(user: User, token: str):
    reset_url = f"{settings.FRONTEND_BASE_URL}/reset_password.html?token={token}"
    subject = "Reset your Codavatar InternTrack password"
    message = f"Hello {user.full_name},\n\nReset your password using this link:\n{reset_url}\n\n- Codavatar Tech"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def send_credentials_email(user: User, password: str):
    subject = "Your Codavatar InternTrack Login Credentials"
    message = (
        f"Hello {user.full_name},\n\n"
        f"Your account has been created by Codavatar Tech.\n"
        f"Email: {user.email}\n"
        f"Password: {password}\n\n"
        f"Login: {settings.FRONTEND_BASE_URL}/login.html\n\n"
        f"- Codavatar Tech"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(UserMeSerializer(request.user).data)


class SignupView(APIView):
    permission_classes = []
    def post(self, request):
        ser = SignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email = ser.validated_data["email"].lower().strip()
        full_name = ser.validated_data["full_name"].strip()
        role = ser.validated_data["role"]
        password = ser.validated_data["password"]

        if User.objects.filter(email=email).exists():
            return Response({"detail":"Email already exists"}, status=400)

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            is_verified=False,
        )
        send_verification_email(user)
        return Response({"detail":"Signup successful. Check email for verification link."})


class VerifyEmailView(APIView):
    permission_classes = []
    def post(self, request):
        ser = VerifyEmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        token = ser.validated_data["token"]
        try:
            t = EmailVerificationToken.objects.select_related("user").get(token=token, used=False)
        except EmailVerificationToken.DoesNotExist:
            return Response({"detail":"Invalid/expired token"}, status=400)

        t.used = True
        t.save(update_fields=["used"])
        t.user.is_verified = True
        t.user.save(update_fields=["is_verified"])

        return Response({"detail":"Email verified successfully. You can login now."})


# ✅ Verified-only JWT
class VerifiedTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if not user.is_verified:
            raise Exception("Email not verified. Please verify your email first.")
        return data

class VerifiedTokenObtainPairView(TokenObtainPairView):
    serializer_class = VerifiedTokenSerializer


# ✅ Forgot / Reset Password
class ForgotPasswordView(APIView):
    permission_classes = []
    def post(self, request):
        ser = ForgotPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()

        user = User.objects.filter(email=email).first()
        # Always return OK for security (avoid leaking accounts)
        if not user:
            return Response({"detail":"If that email exists, a reset link was sent."})

        token = new_token(16)
        PasswordResetToken.objects.create(user=user, token=token)

        send_reset_email(user, token)
        return Response({"detail":"If that email exists, a reset link was sent."})


class ResetPasswordView(APIView):
    permission_classes = []
    def post(self, request):
        ser = ResetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        token = ser.validated_data["token"]
        new_password = ser.validated_data["new_password"]

        try:
            t = PasswordResetToken.objects.select_related("user").get(token=token, used=False)
        except PasswordResetToken.DoesNotExist:
            return Response({"detail":"Invalid/expired token"}, status=400)

        t.used = True
        t.save(update_fields=["used"])

        u = t.user
        u.set_password(new_password)
        u.save(update_fields=["password"])
        
    

        return Response({"detail":"Password reset successful. You can login now."})
class AdminUsersView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        interns = User.objects.filter(role="INTERN").order_by("full_name")
        supervisors = User.objects.filter(role="SUPERVISOR").order_by("full_name")

        return Response({
            "interns": UserMeSerializer(interns, many=True).data,
            "supervisors": UserMeSerializer(supervisors, many=True).data,
        })


class AdminDeleteUserView(APIView):
    permission_classes = [IsAdmin]

    def delete(self, request, user_id):
        if request.user.id == user_id:
            return Response({"detail": "You cannot delete yourself"}, status=400)

        User.objects.filter(id=user_id).delete()
        return Response({"detail": "User deleted"})