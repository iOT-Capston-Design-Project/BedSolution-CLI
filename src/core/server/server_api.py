import logging
import asyncio
from typing import Optional
from supabase import create_async_client, AsyncClient
import numpy as np
from realtime import RealtimeSubscribeStates

from core.server.models import DayLog, DeviceData, Patient, PressureLog
from core.config import config_manager


class ServerAPI:
    def __init__(self):
        self.supabase_url = config_manager.get_setting("supabase", "url")
        self.supabase_key = config_manager.get_setting("supabase", "api_key")
        self.server_logger = logging.getLogger("server_api")
        self.client: Optional[AsyncClient] = None
        self.device_channels = {}
        # Initialize synchronously on creation
        self._initialize_sync()

    def _initialize_sync(self):
        """Synchronously initialize the client."""
        if not self.supabase_url or not self.supabase_key:
            self.server_logger.error("Supabase URL and API key must be configured")
            self.client = None
            return

        try:
            # Create a new event loop for initialization
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                self.client = loop.run_until_complete(
                    create_async_client(self.supabase_url, self.supabase_key)
                )
                self.server_logger.info("Supabase client initialized successfully")
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as e:
            self.server_logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None

    async def initialize(self):
        if not self.supabase_url or not self.supabase_key:
            self.server_logger.error("Supabase URL and API key must be configured")
            self.client = None
            return self

        self.client = await create_async_client(self.supabase_url, self.supabase_key)
        return self

    @classmethod
    async def create(cls):
        instance = cls()
        await instance.initialize()
        return instance

    async def async_reconnect(self) -> bool:
        self.server_logger.info("Reconnecting to Supabase")
        self.supabase_url = config_manager.get_setting("supabase", "url")
        self.supabase_key = config_manager.get_setting("supabase", "api_key")
        if not self.supabase_url or not self.supabase_key:
            self.server_logger.error("Supabase URL and API key must be configured")
            self.client = None
            return False
        self.client = await create_async_client(self.supabase_url, self.supabase_key)
        return True

    async def async_fetch_device(self, device_id: int) -> Optional[DeviceData]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return None
        try:
            self.server_logger.info(f"Fetching device with id: {device_id}")
            response = await self.client.table("devices").select("*").eq("id", device_id).execute()
            if response.data:
                self.server_logger.info(f"Device found: {device_id}")
                return DeviceData.from_dict(response.data[0])
            self.server_logger.warning(f"Device not found: {device_id}")
            return None
        except Exception as e:
            self.server_logger.error(f"Error fetching device {device_id}: {e}")
            return None

    async def async_create_device(self, device: DeviceData) -> Optional[DeviceData]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return None
        try:
            self.server_logger.info(f"Creating device with id: {device.id}")
            response = await self.client.table("devices").insert(device.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Device created successfully: {device.id}")
                return DeviceData.from_dict(response.data[0])
            self.server_logger.warning(f"Device creation returned no data: {device.id}")
            return None
        except Exception as e:
            self.server_logger.error(f"Error creating device {device.id}: {e}")
            return None

    async def async_remove_device(self, device_id: int) -> bool:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return False
        try:
            self.server_logger.info(f"Removing device with id: {device_id}")
            response = await self.client.table("devices").delete().eq("id", device_id).execute()
            success = len(response.data) > 0
            if success:
                self.server_logger.info(f"Device removed successfully: {device_id}")
            else:
                self.server_logger.warning(f"No device found to remove: {device_id}")
            return success
        except Exception as e:
            self.server_logger.error(f"Error removing device {device_id}: {e}")
            return False

    async def async_fetch_patient_with_device(self, device_id: int) -> Optional[Patient]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return None
        try:
            self.server_logger.info(f"Fetching patient with device_id: {device_id}")
            response = await self.client.table("patients").select().eq("device_id", device_id).execute()
            if response.data:
                self.server_logger.info(f"Patient found for device: {device_id}")
                return Patient.from_dict(response.data[0])
            self.server_logger.warning(f"No patient found for device: {device_id}")
            return None
        except Exception as e:
            self.server_logger.error(f"Error fetching patient with device {device_id}: {e}")
            return None

    async def async_create_daylog(self, daylog: DayLog) -> DayLog:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return daylog
        try:
            self.server_logger.info(f"Creating daylog for device: {daylog.device_id}, day: {daylog.day}")
            response = await self.client.table("day_logs").insert(daylog.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Daylog created successfully: {daylog.id}")
                return DayLog.from_dict(response.data[0])
            self.server_logger.warning(f"Daylog creation returned no data for device: {daylog.device_id}")
            return daylog
        except Exception as e:
            self.server_logger.error(f"Error creating daylog for device {daylog.device_id}: {e}")
            return daylog

    async def async_update_daylog(self, daylog: DayLog) -> Optional[DayLog]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return daylog
        try:
            self.server_logger.info(f"Updating daylog: {daylog.id}")
            response = await self.client.table("day_logs").update(daylog.to_dict()).eq("id", daylog.id).execute()
            if response.data:
                self.server_logger.info(f"Daylog updated successfully: {daylog.id}")
                return DayLog.from_dict(response.data[0])
            self.server_logger.warning(f"Daylog update returned no data: {daylog.id}")
            return daylog
        except Exception as e:
            self.server_logger.error(f"Error updating daylog {daylog.id}: {e}")
            return None

    async def async_fetch_daylogs(self) -> list[DayLog]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return []
        try:
            self.server_logger.info("Fetching all daylogs")
            response = await self.client.table("day_logs").select("*").execute()
            daylogs = [DayLog.from_dict(data) for data in response.data]
            self.server_logger.info(f"Found {len(daylogs)} daylogs")
            return daylogs
        except Exception as e:
            self.server_logger.error(f"Error fetching daylogs: {e}")
            return []

    async def async_create_pressurelog(self, pressurelog: PressureLog) -> Optional[PressureLog]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return pressurelog
        try:
            self.server_logger.info(f"Creating pressurelog for day: {pressurelog.day_id}")
            response = await self.client.table("pressure_logs").insert(pressurelog.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Pressurelog created successfully: {pressurelog.id}")
                return PressureLog.from_dict(response.data[0])
            self.server_logger.warning(f"Pressurelog creation returned no data for day: {pressurelog.day_id}")
            return pressurelog
        except Exception as e:
            self.server_logger.error(f"Error creating pressurelog for day {pressurelog.day_id}: {e}")
            return None

    async def async_update_pressurelog(self, pressurelog: PressureLog) -> Optional[PressureLog]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return pressurelog
        try:
            self.server_logger.info(f"Updating pressurelog: {pressurelog.id}")
            response = await self.client.table("pressure_logs").update(pressurelog.to_dict()).eq("id", pressurelog.id).execute()
            if response.data:
                self.server_logger.info(f"Pressurelog updated successfully: {pressurelog.id}")
                return PressureLog.from_dict(response.data[0])
            self.server_logger.warning(f"Pressurelog update returned no data: {pressurelog.id}")
            return pressurelog
        except Exception as e:
            self.server_logger.error(f"Error updating pressurelog {pressurelog.id}: {e}")
            return None

    async def async_fetch_pressurelogs(self, day_id: int) -> list[PressureLog]:
        if not self.client:
            self.server_logger.error("Supabase client is not initialized")
            return []
        try:
            self.server_logger.info(f"Fetching pressurelogs for day: {day_id}")
            response = await self.client.table("pressure_logs").select("*").eq("day_id", day_id).execute()
            pressurelogs = [PressureLog.from_dict(data) for data in response.data]
            self.server_logger.info(f"Found {len(pressurelogs)} pressurelogs for day: {day_id}")
            return pressurelogs
        except Exception as e:
            self.server_logger.error(f"Error fetching pressurelogs for day {day_id}: {e}")
            return []

    async def update_heatmap(self, device_id: int, heatmap: np.ndarray) -> bool:
        if not self.client:
            return False

        if device_id in self.device_channels:
            try:
                channel = self.device_channels[device_id]
                await channel.send_broadcast(
                    'heatmap_update',
                    {"values": heatmap.flatten().tolist()}
                )
                return True
            except Exception as e:
                self.server_logger.error(f"Error sending heatmap update for device {device_id}: {e}")
                return False

        channel = self.client.channel(f"{device_id}")
        self.device_channels[device_id] = channel

        # Use a synchronous callback that schedules async work
        def _on_subscribed(status: RealtimeSubscribeStates, err: Optional[Exception]):
            if status == RealtimeSubscribeStates.SUBSCRIBED:
                self.server_logger.info(f"Subscribed to channel for device {device_id}")
                # Schedule the async broadcast
                asyncio.create_task(channel.send_broadcast(
                    'heatmap_update',
                    {"values": heatmap.flatten().tolist()}
                ))
            if err:
                self.server_logger.error(f"Error subscribing to channel for device {device_id}: {err}")

        try:
            await channel.subscribe(_on_subscribed)
            return True
        except Exception as e:
            self.server_logger.error(f"Error subscribing to channel for device {device_id}: {e}")
            return False

    def update_heatmap_sync(self, device_id: int, heatmap: np.ndarray) -> bool:
        """Synchronous wrapper for update_heatmap to be used from threads."""
        try:
            # Create new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(self.update_heatmap(device_id, heatmap))
        except Exception as e:
            self.server_logger.error(f"Error in sync heatmap update for device {device_id}: {e}")
            return False

    # Synchronous wrapper methods for backward compatibility
    def _run_async(self, coro):
        """Helper method to run async methods synchronously."""
        try:
            # Check if there's a running loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, use a thread to run the coroutine
                import concurrent.futures
                import threading

                result = None
                exception = None

                def run_in_thread():
                    nonlocal result, exception
                    try:
                        # Create a new event loop for this thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(coro)
                        finally:
                            new_loop.close()
                            asyncio.set_event_loop(None)
                    except Exception as e:
                        exception = e

                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()

                if exception:
                    raise exception
                return result

            except RuntimeError:
                # No running loop, try to get or create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        # Create a new loop if the existing one is closed
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    # No event loop at all, create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                try:
                    return loop.run_until_complete(coro)
                except Exception:
                    # Don't close the loop here to allow reuse
                    raise

        except Exception as e:
            self.server_logger.error(f"Error running async method: {e}")
            raise

    def reconnect(self) -> bool:
        """Synchronous reconnect method."""
        self.server_logger.info("Reconnecting to Supabase")
        self.supabase_url = config_manager.get_setting("supabase", "url")
        self.supabase_key = config_manager.get_setting("supabase", "api_key")
        if not self.supabase_url or not self.supabase_key:
            self.server_logger.error("Supabase URL and API key must be configured")
            self.client = None
            return False

        try:
            # Close existing client if any
            if self.client:
                # Note: AsyncClient may not have a close method,
                # but we'll recreate it anyway
                pass

            # Reinitialize
            self._initialize_sync()
            return self.client is not None
        except Exception as e:
            self.server_logger.error(f"Error reconnecting: {e}")
            return False

    def fetch_device(self, device_id: int) -> Optional[DeviceData]:
        """Synchronous wrapper for async fetch_device."""
        return self._run_async(self.async_fetch_device(device_id))

    def create_device(self, device: DeviceData) -> Optional[DeviceData]:
        """Synchronous wrapper for async create_device."""
        return self._run_async(self.async_create_device(device))

    def remove_device(self, device_id: int) -> bool:
        """Synchronous wrapper for async remove_device."""
        return self._run_async(self.async_remove_device(device_id))

    def fetch_patient_with_device(self, device_id: int) -> Optional[Patient]:
        """Synchronous wrapper for async fetch_patient_with_device."""
        return self._run_async(self.async_fetch_patient_with_device(device_id))

    def create_daylog(self, daylog: DayLog) -> DayLog:
        """Synchronous wrapper for async create_daylog."""
        return self._run_async(self.async_create_daylog(daylog))

    def update_daylog(self, daylog: DayLog) -> Optional[DayLog]:
        """Synchronous wrapper for async update_daylog."""
        return self._run_async(self.async_update_daylog(daylog))

    def fetch_daylogs(self) -> list[DayLog]:
        """Synchronous wrapper for async fetch_daylogs."""
        return self._run_async(self.async_fetch_daylogs())

    def create_pressurelog(self, pressurelog: PressureLog) -> Optional[PressureLog]:
        """Synchronous wrapper for async create_pressurelog."""
        return self._run_async(self.async_create_pressurelog(pressurelog))

    def update_pressurelog(self, pressurelog: PressureLog) -> Optional[PressureLog]:
        """Synchronous wrapper for async update_pressurelog."""
        return self._run_async(self.async_update_pressurelog(pressurelog))

    def fetch_pressurelogs(self, day_id: int) -> list[PressureLog]:
        """Synchronous wrapper for async fetch_pressurelogs."""
        return self._run_async(self.async_fetch_pressurelogs(day_id))