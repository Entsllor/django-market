from core_app.validators import default_image_format_validator, ImageSizeValidator, ForbiddenSymbolsValidator

default_image_format_validator = default_image_format_validator

MIN_PRODUCT_IMAGE_WIDTH = 200
MIN_PRODUCT_IMAGE_HEIGHT = 200
MAX_PRODUCT_IMAGE_WIDTH = 2048
MAX_PRODUCT_IMAGE_HEIGHT = 2048

product_image_size_validator = ImageSizeValidator(
    min_image_width=MIN_PRODUCT_IMAGE_WIDTH,
    min_image_height=MIN_PRODUCT_IMAGE_HEIGHT,
    max_image_width=MAX_PRODUCT_IMAGE_WIDTH,
    max_image_height=MAX_PRODUCT_IMAGE_HEIGHT
)

MIN_MARKET_LOGO_WIDTH = 200
MIN_MARKET_LOGO_HEIGHT = 200
MAX_MARKET_LOGO_WIDTH = 2048
MAX_MARKET_LOGO_HEIGHT = 2048

market_logo_size_validator = ImageSizeValidator(
    min_image_width=MIN_PRODUCT_IMAGE_WIDTH,
    min_image_height=MIN_PRODUCT_IMAGE_HEIGHT,
    max_image_width=MAX_PRODUCT_IMAGE_WIDTH,
    max_image_height=MAX_PRODUCT_IMAGE_HEIGHT
)

product_attributes_symbols_validator = ForbiddenSymbolsValidator(r"[^\w\s']")
product_type_property_symbols_validator = ForbiddenSymbolsValidator(r'[^\w\' ]')
