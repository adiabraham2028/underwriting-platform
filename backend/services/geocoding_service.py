import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

logger = logging.getLogger(__name__)

geocoder = Nominatim(user_agent="underwriting-platform")


async def geocode_address(address: str, city: str, state: str, zip_code: str) -> tuple[float | None, float | None]:
    """Geocode an address and return (lat, lng) or (None, None) on failure."""
    query = f"{address}, {city}, {state} {zip_code}"
    try:
        location = geocoder.geocode(query, timeout=10)
        if location:
            return location.latitude, location.longitude
        logger.warning(f"No geocoding result for: {query}")
        return None, None
    except (GeocoderServiceError, GeocoderTimedOut) as e:
        logger.warning(f"Geocoding failed for {query}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected geocoding error for {query}: {e}")
        return None, None
