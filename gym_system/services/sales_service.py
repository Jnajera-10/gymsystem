from database.models.sales import Sale, SaleItem
from database.models.inventory import Product
from database.db import db
from services.inventory_service import InventoryService

class SalesService:
    @staticmethod
    def create_sale(client_id, items_data, payment_method, notes=None,
                    customer_name=None, created_by=None):
        # Validar stock de todos los productos ANTES de escribir nada
        for item in items_data:
            product = Product.query.get(item['product_id'])
            if not product:
                raise ValueError(f'Producto {item["product_id"]} no encontrado.')
            if product.quantity < item['quantity']:
                raise ValueError(f'Stock insuficiente para "{product.name}". '
                                 f'Disponible: {product.quantity}, solicitado: {item["quantity"]}.')

        try:
            total = 0
            # Si hay cliente registrado se ignora el nombre libre
            sale = Sale(client_id=client_id, payment_method=payment_method, notes=notes, total=0,
                        customer_name=None if client_id else customer_name,
                        created_by=created_by)
            db.session.add(sale)
            db.session.flush()

            for item in items_data:
                product = Product.query.get(item['product_id'])
                subtotal = product.sale_price * item['quantity']
                total += subtotal
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=product.sale_price,
                    subtotal=subtotal
                )
                db.session.add(sale_item)
                # Descontar stock dentro de la misma sesión (sin commit interno)
                product.quantity -= item['quantity']
                mov_class = InventoryService.build_movement(product.id, item['quantity'], 'Venta')
                db.session.add(mov_class)

            sale.total = total
            db.session.commit()
            return sale

        except Exception:
            db.session.rollback()
            raise
