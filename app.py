from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a secure random key
app.config['MONGO_URI'] = 'mongodb+srv://test:sparta@cluster0.zm8eqgi.mongodb.net/techtrade'
app.config['MONGO_DBNAME'] = 'techtrade'
app.config['UPLOAD_FOLDER'] = 'static/uploaded_img'

mongo = PyMongo(app)

@app.route('/')
def hello():
    products = mongo.db.products.find()
    return render_template('index.html',products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'customer'  # Default role is 'user'

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        user_data = {
            'username': username,
            'password': hashed_password,
            'role': role
        }

        mongo.db.users.insert_one(user_data)
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = mongo.db.users.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            if session['role'] == 'admin':
                return redirect(url_for('adminDashboard'))
    
        return redirect(url_for('customerDashboard'))

        return 'Invalid username or password'

    return render_template('login.html')

# Route to add a product to the cart
@app.route('/add_to_cart/<product_id>', methods=['GET'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        total_quantity = 1
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            # Handle the case where the product is not found
            return redirect(url_for('hello'))

        product_name = product['product_name']
        price = product['price']

        # Check if the product is already in the user's cart
        cart_item = mongo.db.carts.find_one({
            'user_id': session['user_id'],
            'product_id': ObjectId(product_id)
        })

        total_harga_produk = total_quantity * price

        if cart_item:
            # If the product is already in the cart, update the quantity and total price
            jumlah_sebelumnya = cart_item['quantity']
            total_harga_sebelumnya = cart_item['price']

            total_harga_baru = total_harga_sebelumnya + total_harga_produk
            jumlah_baru = jumlah_sebelumnya + total_quantity

            mongo.db.carts.update_one(
                {
                    'user_id': session['user_id'],
                    'product_id': ObjectId(product_id)
                },
                {'$set': {'quantity': jumlah_baru, 'price': total_harga_baru}}
            )

        else:  # If the product is not in the cart, add a new product
            cart_item = {
                "user_id": session["user_id"],
                "product_id": ObjectId(product_id),
                "product_name": product["product_name"],
                "product_image_path": product["product_image_path"],
                "price": total_harga_produk,
                "quantity": total_quantity,
            }
            mongo.db.carts.insert_one(cart_item)

        flash('Product placed successfully!', 'success')
        return redirect(url_for('customerDashboard'))
        
@app.route('/update_to_cart/<product_id>', methods=['POST'])
def update_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        total_quantity = int(request.form['total_quantity'])
    # Find the product by its ObjectId
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            # Handle the case where the product is not found
            return redirect(url_for('hello'))

        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        price = product['price']

        mongo.db.carts.update_one({'product_id': ObjectId(product_id)}, {
            "$set": {"quantity": total_quantity, "price": price * total_quantity}
        })
        flash('Cart Success Updated!', 'success')
        return redirect(url_for('cart'))

@app.route('/delete_to_cart/<product_id>', methods=['GET'])
def delete_to_cart(product_id):
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    mongo.db.carts.delete_one({"product_id": ObjectId(product_id), "user_id": session.get('user_id')})
    flash('Deleted cart successfully!', 'success')
    return redirect(url_for("cart"))

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Retrieve user's cart items from the carts collection
    user_id = session['user_id']
    cart_items_cursor = mongo.db.carts.find({'user_id': user_id})
    cart_items = list(cart_items_cursor)

    # Calculate the total price
    total_price = sum(int(item['price']) for item in cart_items)
    total_quantity = sum(int(item['quantity']) for item in cart_items)

    if request.method == 'POST':
        # Process the order and clear the cart
        user_name = session['username']
        order_time = datetime.now()
        total_products = len(cart_items)
        payment_method = request.form.get('payment_method', 'Not specified')

        # Create a report in the orders collection
        order_data = {
            'user_name': user_name,
            'order_time': order_time,
            'total_products': total_products,
            'total_price': total_price,
            'payment_method': payment_method,
            'status': "new"
        }

        mongo.db.orders.insert_one(order_data)

        # Clear the user's cart
        mongo.db.carts.delete_many({'user_id': user_id})

        flash('Order placed successfully!', 'success')
        return redirect(url_for('cart'))

    # Render the cart template with the list of cart items and total price
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, total_quantity=total_quantity)

# Route to add a product to favorites
@app.route('/add_to_favorites/<product_id>', methods=['GET'])
def add_to_favorites(product_id):
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Find the product by its ObjectId
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        # Handle the case where the product is not found
        return redirect(url_for('products'))
    

    # Create a favorites item
    favorites_item = {
        "user_id": session["user_id"],
        "product_id": product["_id"],
        "product_name": product["product_name"],
        "product_image_path": product["product_image_path"],
        "price": product["price"],
    }

    # print(favorites_item)
    # Add the favorites item to the favorites collection
    mongo.db.favorites.insert_one(favorites_item)

    # Redirect to the product listing page or wherever you want
    return redirect(url_for('customerDashboard'))

@app.route('/delete_to_favorites/<product_id>', methods=['GET'])
def delete_to_favorites(product_id):
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    mongo.db.favorites.delete_one({"product_id": ObjectId(product_id), "user_id": session.get('user_id')})
    flash('Deleted favorite successfully!', 'success')
    return redirect(url_for("favorites"))

# Route to show favorite products
@app.route('/favorites')
def favorites():
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Retrieve user's favorite products from the favorites collection
    user_id = session['user_id']
    favorites = mongo.db.favorites.find({'user_id': user_id})

    # Render the favorites template with the list of favorite products
    return render_template('favorites.html', favorites=favorites)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def adminDashboard():
    if session['role'] == 'admin':
        return render_template('admindashboard.html')
    return 'Access Denied'

@app.route('/customer/dashboard')
def customerDashboard():
    products = mongo.db.products.find()
    if session['role'] == 'customer':
        return render_template('customer.html', products=products)
    return 'Access Denied'

@app.route('/admin/products', methods=['GET', 'POST'])
def products():
    if session["role"] != "admin":
        return "Access Denied"
    if request.method == "POST":
        # Get product data from the form
        product_id = request.form.get("product_id")
        product_name = request.form.get("product_name")
        price = int(request.form.get("price"))
        category = request.form.get("category")

        # Check if the 'product_image' file is present in the form
        if "product_image" in request.files:
            product_image = request.files["product_image"]

            # Save the file to the 'uploads' folder
            upload_folder = app.config["UPLOAD_FOLDER"]
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            filename = secure_filename(product_image.filename)
            print(filename)
            product_image_path = os.path.join(upload_folder, filename).replace(
                "\\", "/"
            )
            product_image.save(product_image_path)
            print(product_image_path)
            # print(product_image_path)
            product_image_path = product_image_path.replace("static/", "")
        else:
            # Handle the case where no image is provided
            product_image_path = None

        # Create a dictionary representing the product
        product_data = {
            "product_name": product_name,
            "product_image_path": product_image_path,
            "price": price,
            "category": category,
        }

        # Insert or update the product data into the 'products' collection
        if product_id:
            # If product_id is present, update the existing product
            mongo.db.products.update_one(
                {"_id": ObjectId(product_id)}, {"$set": product_data}
            )
        else:
            # If product_id is not present, insert a new product
            mongo.db.products.insert_one(product_data)

        # Redirect to the product listing page or wherever you want
        return redirect(url_for("products"))

    # Display the product listing page
    products = mongo.db.products.find()
    return render_template("products.html", products=products)

# Render edit.html for editing a product
@app.route('/admin/edit_product/<product_id>', methods=['GET'])
def edit_product(product_id):
    if session['role'] != 'admin':
       return 'Access Denied'
    # Find the product by its ObjectId
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        # Handle the case where the product is not found
        return redirect(url_for('products'))

    # Render the edit.html template with the product data
    return render_template('edit.html', product=product)

# Handle form submission for updating a product
@app.route('/admin/edit_product/<product_id>', methods=['POST'])
def update_product(product_id):
    if session['role'] != 'admin':
       return 'Access Denied'
    # Find the product by its ObjectId
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        # Handle the case where the product is not found
        return redirect(url_for('products'))

    # Get updated product data from the form
    product_name = request.form.get('product_name')
    price = request.form.get('price')
    category = request.form.get('category')

    # Check if the 'product_image' file is present in the form
    if 'product_image' in request.files:
        product_image = request.files['product_image']

        # Save the file to the 'uploads' folder
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        filename = secure_filename(product_image.filename)
        product_image_path = os.path.join(upload_folder, filename).replace(
                "\\", "/"
            )
        product_image.save(product_image_path)
        product_image_path = product_image_path.replace("static/", "")

        # Update the product image path
        mongo.db.products.update_one({'_id': ObjectId(product_id)}, {'$set': {'product_image_path': product_image_path}})

    # Update other product fields
    mongo.db.products.update_one({'_id': ObjectId(product_id)}, {'$set': {'product_name': product_name, 'price': price, 'category': category}})

    # Redirect to the product listing page or wherever you want
    return redirect(url_for('products'))

# Route to delete a product
@app.route('/admin/delete_product/<product_id>', methods=['GET'])

def delete_product(product_id):
    if session['role'] != 'admin':
       return 'Access Denied'
    # Find the product by its ObjectId
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        # Handle the case where the product is not found
        return redirect(url_for('products'))

    # Delete the product from the database
    mongo.db.products.delete_one({'_id': ObjectId(product_id)})
    mongo.db.favorites.delete_many({'product_id': ObjectId(product_id)})
    mongo.db.carts.delete_many({'product_id': ObjectId(product_id)})

    # Optionally, delete the associated image file from the server
    if 'product_image_path' in product:
        image_path = product['product_image_path']
        if os.path.exists(image_path):
            os.remove(image_path)

    # Redirect to the product listing page or wherever you want
    return redirect(url_for('products'))

@app.route('/admin/orders')
def orders():
    if session['role'] != 'admin':
       return 'Access Denied'
    # Retrieve all orders from the orders collection
    orders_cursor = mongo.db.orders.find()
    orders = list(orders_cursor)
    mongo.db.orders.update_many(
        {
            "status": "new"
        },
        {
            "$set": {'status': 'old'}
        }
    )
    return render_template('order.html', orders=orders)

@app.route('/admin/messages')
def show_messages():
    if session['role'] != 'admin':
       return 'Access Denied'
    # Retrieve all messages from the contact collection
    messages_cursor = mongo.db.messages.find()
    messages = list(messages_cursor)
    mongo.db.messages.update_many(
        {
            "status": "new"
        },
        {
            "$set": {'status': 'old'}
        }
    )
    # Render the template with the list of messages
    return render_template('messages.html', messages=messages)

@app.route('/get_new_message')
def get_new_message():
    count = mongo.db.messages.count_documents({ 'status': 'new' })
    response = {'count': count}
    return response, 200

@app.route('/contact', methods=[ 'POST'])
def contact():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        number = request.form.get('number')
        message = request.form.get('message')

        # Save the message to the messages collection
        mongo.db.messages.insert_one({
            'name': name,
            'email': email,
            'number': number,
            'message': message,
            'status': 'new',
            'timestamp': datetime.utcnow()
        })

        # Redirect to a thank you or confirmation page
        flash('Message successfully sent!', 'success')
        return redirect(url_for('customerDashboard'))

@app.route('/get_new_orders')
def get_new_orders():
    count = mongo.db.orders.count_documents({ 'status': 'new' })
    response = {'count': count}
    return response, 200

if __name__ == '__main__':
    app.run(debug=True)