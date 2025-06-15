"""
    These following are the possible statuses and it's number we will received from Flash Express webhook:
        1=Picked Up (รับพัสดุแล้ว)
        2=In transit (ระหว่างการขนส่ง)
        3=Delivering (ระหว่างการจัดส่ง)
        4=Detained (พัสดุคงคลัง)
        5=Signed (เซ็นรับแล้ว)
        6=Problem shipment being processed (ระหว่างจัดการพัสดุมีปัญหา)
        7=Returned shipment (พัสดุตีกลับแล้ว)
        8=Close by exception (ปิดงานมีปัญหา)
        9=Cancelled (เรียกคืนพัสดุแล้ว)
    """
part_corner_wip_and_task_status = [
    ('order_received', 'Order Received'),
    ('kitting', 'Kitting'),
    ('checking', 'Checking'),
    ('packing', 'Packing'),
    ('cancelled', 'Cancelled'),
    ('done', 'Done')
]

flash_express_wip_and_task_good_status = [
    ('pending', 'Pending'), # indicate the process not reach to Flash Express
    ('delivery_order_created', 'Delivery Order Created'),
    ('courier_pickup_requested', 'Courier Pickup Requested'),
    ('pick_up_by_courier', 'Pick Up By Courier'),
    ('in_transit', 'In Transit'),
    ('delivering', 'Delivering'),
    ('signed', 'Signed'),
]

flash_express_wip_and_task_bad_status = [
    ('detained', 'Detained'),
    ('problem_shipment_being_processed', 'Problem Shipment Being Processed'),
    ('returned_shipment', 'Returned Shipment'),
    ('close_by_exception', 'Close By Exception'),
    ('cancelled', 'Cancelled'),
]

part_corners_pickup_request_status = [
    ('draft', 'Draft'),
    ('pickup_request_created', 'Pickup Request Created'),
]

flash_express_pickup_request_status = [
    ('pending', 'Pending'), # indicate the process not reach to Flash Express
    ('awaiting_allocation', 'Awaiting Allocation'),
    ('awaiting_to_pickup', 'Awaiting To Pickup'),
    ('picked_up', 'Picked Up'),
    ('task_handovered', 'Task Handovered'),
    ('cancelled', 'Cancelled'),
]


"""
This map is used to display the status of the sale order in the customer portal.
"""
sale_portal_status_display_map = {
            'order_received': 'Preparing',
            'kitting': 'Preparing',
            'checking': 'Preparing',
            'packing': 'Packing',
            'delivery_order_created': 'Ready to ship',
            'courier_pickup_requested': 'Courier is going to pick up',
            'pick_up_by_courier': 'Courier picked up',
            'in_transit': 'In Transit',
            'delivering': 'Delivering',
            'detained': 'Detained',
            'signed': 'Delivered',
            'problem_shipment_being_processed': 'Problem Shipment Being Processed',
            'returned_shipment': 'Returned Shipment',
            'close_by_exception': 'Close By Exception',
            'cancelled': 'Cancelled',
            'done': 'Delivered'
        }