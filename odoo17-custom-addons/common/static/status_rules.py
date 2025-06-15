"""
Because of the Flash Express status , we do not know how they transition the status, 
so I define with no backward and forward transition constraint.
In contrast for internal statuses (  'order_received', 'kitting', 'checking', 'packing', etc. ), it need to have a constraint that
"""
wip_and_task_allowed_status_transition = {
    'order_received': ['kitting'],
    'kitting': ['checking'],
    'checking': ['packing'],
    'packing': ['done'], # packing can be transitioned to done when order is signed by customer
    # For the delivery statuses, each can transition to any other delivery status.
    # The key itself is excluded from its own list of possible transitions.
    'pending': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering',
        'detained', 'signed', 'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception',
        'cancelled', 'done'
    ],
    'delivery_order_created': [
        'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'courier_pickup_requested': [
        'delivery_order_created', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'pick_up_by_courier': [
        'delivery_order_created', 'courier_pickup_requested', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'in_transit': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'delivering': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'detained': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    # 'signed' is a terminal state and has no further transitions.
    'signed': [],
    'problem_shipment_being_processed': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'returned_shipment': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'close_by_exception', 'cancelled', 'done'
    ],
    'close_by_exception': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'cancelled', 'done'
    ],
    'cancelled': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'done'
    ],
    # 'done' is a terminal state and has no further transitions.
    'done': []
} 

pickup_request_allowed_status_transition = {
    'draft': ['awaiting_allocation'],
    'awaiting_allocation': ['awaiting_to_pickup', 'cancelled'],
    'awaiting_to_pickup': ['picked_up', 'cancelled'],
    'picked_up': ['task_handovered', 'cancelled'],
    'task_handovered': ['cancelled'],
    'cancelled': [],
}