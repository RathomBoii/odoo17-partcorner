def part_corners_and_flash_express_wip_and_task_status_mapper(flash_express_delivery_status: int) -> str:
    """
    Map Flash Express delivery status to Part Corners status.
    """
    flash_express_status_map = {
        1: 'pick_up_by_courier',  # Picked Up
        2: 'in_transit',          # In transit
        3: 'delivering',          # Delivering
        4: 'detained',            # Detained
        5: 'signed',              # Signed
        6: 'problem_shipment_being_processed',  # Problem shipment being processed
        7: 'returned_shipment',   # Returned shipment
        8: 'close_by_exception',   # Close by exception
        9: 'cancelled'             # Cancelled
    }


    try:
        return flash_express_status_map[flash_express_delivery_status]
    except KeyError:
        raise ValueError(f"Unknown Flash Express delivery status: {flash_express_delivery_status}")
    
def part_corners_and_flash_express_pickup_request_status_mapper(flash_express_pickup_request_status: int) -> str:
    """
    Map Flash Express pickup request status to Part Corners status.
    """
    flash_express_pickup_request_map = {
        0: 'awaiting_allocation',  
        1: 'awaiting_to_pickup',
        2: 'picked_up',
        3: 'task_handovered',
        4: 'cancelled',
    }

    try:
        return flash_express_pickup_request_map[flash_express_pickup_request_status]
    except KeyError:
        raise ValueError(f"Unknown Flash Express pickup request status: {flash_express_pickup_request_status}")