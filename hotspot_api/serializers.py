# hotspot_api/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    AccessPoint, 
    Device, 
    UsageData, 
    MpesaTransaction, 
    Voucher,
    # 💥 ADDED: The missing HotspotPlan model
    HotspotPlan, 
)

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the Django User model.
    """
    class Meta:
        model = User
        fields = '__all__'

class HotspotPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for the HotspotPlan model.
    This is the serializer you were missing for your front-end view!
    """
    class Meta:
        model = HotspotPlan
        fields = '__all__'

class AccessPointSerializer(serializers.ModelSerializer):
    """
    Serializer for the AccessPoint model.
    """
    class Meta:
        model = AccessPoint
        fields = '__all__'

class DeviceSerializer(serializers.ModelSerializer):
    """
    Serializer for the Device model.
    """
    class Meta:
        model = Device
        fields = '__all__'

class UsageDataSerializer(serializers.ModelSerializer):
    """
    Serializer for the UsageData model.
    """
    # 💡 Enhancement: Include a read-only field for the username instead of just the user ID
    # user_details = serializers.CharField(source='user.username', read_only=True) 

    class Meta:
        model = UsageData
        fields = '__all__'
        # fields = ['id', 'user', 'access_point', 'data_used', 'start_time', 'end_time', 'user_details']

class MpesaTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for the MpesaTransaction model.
    """
    class Meta:
        model = MpesaTransaction
        fields = '__all__'

class VoucherSerializer(serializers.ModelSerializer):
    """
    Serializer for the Voucher model.
    """
    class Meta:
        model = Voucher
        fields = '__all__'