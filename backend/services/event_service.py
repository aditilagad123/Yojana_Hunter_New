import json
import queue
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class EventService:
    """
    Lightweight, thread-safe in-memory SSE event bus for real-time dashboard notifications.
    Enables instant updates when payments are verified, approved, or rejected without page refreshes.
    """
    _subscribers: Dict[int, List[queue.Queue]] = {}
    _admin_subscribers: List[queue.Queue] = []

    @classmethod
    def subscribe_user(cls, user_id: int) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=50)
        if user_id not in cls._subscribers:
            cls._subscribers[user_id] = []
        cls._subscribers[user_id].append(q)
        return q

    @classmethod
    def unsubscribe_user(cls, user_id: int, q: queue.Queue):
        if user_id in cls._subscribers:
            try:
                cls._subscribers[user_id].remove(q)
            except ValueError:
                pass
            if not cls._subscribers[user_id]:
                del cls._subscribers[user_id]

    @classmethod
    def subscribe_admin(cls) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=50)
        cls._admin_subscribers.append(q)
        return q

    @classmethod
    def unsubscribe_admin(cls, q: queue.Queue):
        try:
            cls._admin_subscribers.remove(q)
        except ValueError:
            pass

    @classmethod
    def publish_to_user(cls, user_id: int, event_data: Dict[str, Any]):
        """Publish event to all active SSE connections for a specific citizen."""
        msg = json.dumps(event_data)
        for q in list(cls._subscribers.get(user_id, [])):
            try:
                q.put_nowait(msg)
            except queue.Full:
                logger.warning(f"Subscriber queue full for user {user_id}, dropping message.")

    @classmethod
    def publish_to_admin(cls, event_data: Dict[str, Any]):
        """Publish event to all active admin dashboard connections."""
        msg = json.dumps(event_data)
        for q in list(cls._admin_subscribers):
            try:
                q.put_nowait(msg)
            except queue.Full:
                logger.warning("Admin subscriber queue full, dropping message.")

    @classmethod
    def get_next_event(cls, q: queue.Queue, timeout: float = 20.0):
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    @classmethod
    def broadcast_subscription_event(cls, user_id: int, event_type: str, data: Dict[str, Any]):
        """Sends event to the specific citizen and to administrators simultaneously."""
        payload = {
            "type": event_type,
            "userId": user_id,
            "data": data
        }
        cls.publish_to_user(user_id, payload)
        cls.publish_to_admin(payload)
