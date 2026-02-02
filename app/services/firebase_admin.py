import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class FirebaseAdminService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseAdminService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            self.__class__._initialized = True

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase app is already initialized
            try:
                firebase_admin.get_app()
                print("✅ Firebase Admin SDK already initialized")
                return
            except ValueError:
                # App doesn't exist, initialize it
                pass
            
            # Get credentials path from environment
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "./firebase-service-account.json")
            
            if not os.path.exists(cred_path):
                print(f"⚠️  Firebase credentials file not found at: {cred_path}")
                print("   Push notifications will not work until you add the service account JSON")
                return

            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing Firebase Admin SDK: {e}")

    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str] = None,
        channel_id: str = 'relact_default'
    ) -> bool:
        """
        Send notification to a single device
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            channel_id: Android Notification Channel ID
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Ensure data contains channel_id for local handling
            msg_data = data or {}
            msg_data['channel_id'] = channel_id
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=msg_data,
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        priority='high',
                        channel_id=channel_id,
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                        ),
                    ),
                ),
            )

            response = messaging.send(message)
            print(f"✅ Notification sent successfully: {response}")
            return True
        except Exception as e:
            print(f"❌ Error sending notification: {e}")
            return False

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str] = None,
        channel_id: str = 'relact_default'
    ) -> Dict[str, Any]:
        """
        Send notification to multiple devices
        
        Args:
            tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            channel_id: Android Notification Channel ID
            
        Returns:
            dict: Response with success and failure counts
        """
        success_count = 0
        failure_count = 0
        responses = []
        
        # Ensure data contains channel_id for local handling
        msg_data = data or {}
        msg_data['channel_id'] = channel_id
        
        # Send to each token individually to avoid batch API issues
        for token in tokens:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=msg_data,
                    token=token,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            sound='default',
                            priority='high',
                            channel_id=channel_id,
                        ),
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound='default',
                            ),
                        ),
                    ),
                )

                response = messaging.send(message)
                success_count += 1
                responses.append({
                    "success": True,
                    "message_id": response,
                    "error": None
                })
                print(f"✅ Notification sent to device: {response}")
            except Exception as e:
                failure_count += 1
                responses.append({
                    "success": False,
                    "message_id": None,
                    "error": str(e)
                })
                print(f"❌ Error sending to device: {e}")
        
        print(f"✅ Multicast complete: {success_count} success, {failure_count} failures")
        
        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "responses": responses
        }

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Dict[str, str] = None,
        channel_id: str = 'relact_default'
    ) -> bool:
        """
        Send notification to a topic (for broadcast)
        
        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Additional data payload
            channel_id: Android Notification Channel ID
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Ensure data contains channel_id for local handling
            msg_data = data or {}
            msg_data['channel_id'] = channel_id
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=msg_data,
                topic=topic,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        priority='high',
                        channel_id=channel_id,
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                        ),
                    ),
                ),
            )

            response = messaging.send(message)
            print(f"✅ Topic notification sent successfully: {response}")
            return True
        except Exception as e:
            print(f"❌ Error sending topic notification: {e}")
            return False


# Singleton instance
firebase_service = FirebaseAdminService()
