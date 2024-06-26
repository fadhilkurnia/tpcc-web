from datetime import datetime
from random import randint, choice

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from tpcc.models import *
from tpcc.settings import WAREHOUSES


def new_order_tran(w_id, c_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    whouse = session.query(Warehouse).filter(Warehouse.id == w_id).first()
    district = choice(whouse.districts.all())
    customer = session.query(Customer).filter(Customer.id == c_id).first()
    ol_cnt = randint(1, 10)
    amount = randint(1, 10)

    order = Order(
        ol_cnt=ol_cnt,
        customer_id=customer.id,
        entry_d=datetime.now(),
        warehouse=whouse,
        district=district
    )
    session.add(order)
    items_id = []

    for i in range(ol_cnt):
        item = session.query(Item).filter(Item.id == randint(1, WAREHOUSES * 10)).first()
        items_id.append(item.id)
        ord_line = OrderLine(
            item=item,
            amount=amount,
            order=order
        )
        session.add(ord_line)

    stocks = session.query(Stock).filter(Stock.warehouse_id == whouse.id, Stock.item_id.in_(items_id)).order_by(
        text("id")).with_for_update().all()
    for stock in stocks:
        i_in_o = items_id.count(stock.item_id)
        stock.order_cnt += 1
        stock.quantity -= amount * i_in_o
    session.commit()
    response = model_as_dict(order)
    session.close()

    return response


def payment_tran(w_id, c_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    whouse = session.query(Warehouse).filter(Warehouse.id == w_id).first()
    district = choice(whouse.districts.all())
    customer = session.query(Customer).filter(Customer.id == c_id).first()
    h_amount = randint(10, 5000)

    whouse.ytd += h_amount
    district.ytd += h_amount
    customer.balance -= h_amount
    customer.ytd_payment += h_amount
    customer.payment_cnt += 1

    history = History(
        amount=h_amount,
        data='new_payment',
        date=datetime.now(),
        customer=customer,
    )

    session.add(history)
    session.commit()
    response = model_as_dict(history)
    session.close()

    return response


def order_status_tran(c_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    customer = session.query(Customer).filter(Customer.id == c_id).first()
    last_order = session.query(Order).filter(Order.customer == customer).order_by(text("id desc")).first()
    orders = []

    if not last_order:
        session.commit()
        return False

    for ol in last_order.o_lns:
        orders.append({
            'ol_delivery_d': ol.delivery_d,
            'ol_item': model_as_dict(ol.item),
            'ol_amount': ol.amount,
            'ol_order': model_as_dict(ol.order)
        })
    session.commit()
    session.close()

    return orders


def delivery_tran(w_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    whouse = session.query(Warehouse).filter(Warehouse.id == w_id).first()
    districts = session.query(District).filter(District.warehouse == whouse).order_by(text("id")).with_for_update()

    customers_id = []
    for district in districts:
        order = (session.query(Order).filter(Order.district == district, Order.is_o_delivered == False)
                 .order_by(text("id")).first())

        if not order:
            continue

        order.is_o_delivered = True

        for o_l in order.o_lns:
            o_l.delivery_d = datetime.now()
        customers_id.append(order.customer_id)

    customers = session.query(Customer).filter(Customer.id.in_(customers_id)).order_by(text("id")).with_for_update()
    for customer in customers:
        amount = customers_id.count(customer.id)
        customer.delivery_cnt += amount
    session.commit()
    session.close()

    return True


def stock_level_tran(w_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    whouse = session.query(Warehouse).filter(Warehouse.id == w_id).first()

    items_stock = {}
    for order in session.query(Order).filter(Order.warehouse == whouse).order_by(text("id desc"))[:20]:
        for ol in order.o_lns:
            item = session.query(Item).filter(Item.id == ol.item_id).first()
            if item.name in items_stock.keys():
                continue
            stock = session.query(Stock).filter(Stock.warehouse == whouse, Stock.item == item).first()
            items_stock[item.name] = stock.quantity
    session.commit()
    session.close()

    return items_stock
