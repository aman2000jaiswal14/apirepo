import firebase_admin
from firebase_admin import credentials, db, auth
from flask import Flask, request, jsonify
import traceback
import os
import time
# -----------------------------
# 🔥 FIREBASE INITIALIZATION
# -----------------------------
try:
    cred_path = os.path.join(os.path.dirname(__file__), "firebase.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(
        cred,
        {"databaseURL": "https://myproject-b3962-default-rtdb.firebaseio.com/"}
    )
    print("🔥 Firebase connected to:", firebase_admin.get_app().project_id)
except Exception as e:
    print("❌ Firebase Initialization Error:", e)
    exit(1)

app = Flask(__name__)
print("Firebase app:", firebase_admin.get_app().project_id)

# -----------------------------
# 🔥 HELPER FUNCTIONS
# -----------------------------
def safe_json_response(status, message, data=None, code=200):
    if data is None:
        data = {}
    return jsonify({"status": status, "message": message, "data": data}), code

def get_json_data():
    """Safely parse JSON from request"""
    try:
        data = request.get_json(force=True)
        if isinstance(data, str):
            return {"value": data}
        return data
    except Exception:
        return {}

def safe_append(lst, val):
    """Append to list if not already present"""
    if val not in lst:
        lst.append(val)

def wrap_data(key, value):
    """Wrap list or dict in a consistent data object"""
    return {key: value if value is not None else []}

# -----------------------------
# 🔥 LOG REQUEST
# -----------------------------
@app.before_request
def log_request_info():
    if request.method in ["POST", "PUT"]:
        try:
            print(f"🔥 Incoming {request.path} JSON: {request.get_json(force=True)}")
        except Exception:
            print("❌ Failed to parse JSON for logging")

# -----------------------------
# 🔥 BASIC ROUTE
# -----------------------------
@app.route("/", methods=["GET"])
def check():
    return safe_json_response("success", "API running OK")

# -----------------------------
# 🔥 USERS
# -----------------------------
@app.route("/users/create", methods=["POST"])
def create_user():
    try:
        data = get_json_data()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        mobileNo = data.get("mobileNo", "")
        groupIds = data.get("groupIds", [])

        if not name or not email or not password:
            return safe_json_response("error", "Missing required fields", code=400)

        try:
            user_record = auth.create_user(email=email, password=password, display_name=name)
            uid = user_record.uid
        except auth.EmailAlreadyExistsError:
            return safe_json_response("error", "Email already exists", code=400)
        except Exception as e:
            return safe_json_response("error", f"Firebase Auth error: {str(e)}", code=500)

        email_key = email.replace(".", "_dot_").replace("@", "_at_")
        db.reference(f"users/{uid}").set({
            "userId": uid,
            "name": name,
            "email": email,
            "mobileNo": mobileNo,
            "groupIds": groupIds
        })
        db.reference(f"usersAsEmailKey/{email_key}").set({"email": email_key, "userId": uid})

        return safe_json_response("success", "User created", {"userId": uid}, 201)
    except Exception:
        return safe_json_response("error", "Failed to create user", traceback.format_exc(), 500)

@app.route("/users/login", methods=["POST"])
def login_user():
    try:
        data = get_json_data()
        email = data.get("email")
        # Firebase Admin cannot verify password, so just check existence
        try:
            user = auth.get_user_by_email(email)
            return safe_json_response("success", "User exists", {"userId": user.uid})
        except auth.UserNotFoundError:
            return safe_json_response("error", "Invalid email", code=404)
    except Exception:
        return safe_json_response("error", "Login failed", traceback.format_exc(), 500)


@app.route("/users/logout", methods=["POST"])
def logout_user():
    try:
        # No server-side logout (Firebase Admin cannot do this)
        # Just respond success so client can clear local session
        return safe_json_response("success", "User logged out")
    except Exception:
        return safe_json_response("error", "Logout failed", traceback.format_exc(), 500)



@app.route("/users", methods=["GET"])
def get_users():
    try:
        users = db.reference("users").get() or {}
        result = [{**v, "userId": k} for k, v in users.items()]
        return safe_json_response("success", "Users fetched", wrap_data("users", result))
    except Exception:
        return safe_json_response("error", "Failed to fetch users", traceback.format_exc(), 500)

@app.route("/users/groups", methods=["POST"])
def get_user_groups():
    try:
        data = get_json_data()
        
        userId = data.get("userId") or data.get("value")
        print(f"get user group data : :  {data}")
        
        user = db.reference(f"users/{userId}").get()
        print(user)
        if not user:
            return safe_json_response("error", "User not found", code=404)
        group_ids = user.get("groupIds") or []
        print(group_ids)
        return safe_json_response("success", "User groups fetched", wrap_data("groups", group_ids))
    except Exception:
        return safe_json_response("error", "Failed to fetch user groups", traceback.format_exc(), 500)


@app.route("/users/<userId>", methods=["GET"])
def get_user_by_id(userId):
    try:
        print(userId)
        user = db.reference(f"users/{userId}").get()
        print(user)
        if not user:
            return safe_json_response("error", "User not found", code=404)
        user["userId"] = userId
        return safe_json_response("success", "User fetched", {"user": user})
    except Exception:
        return safe_json_response("error", "Failed to fetch user", traceback.format_exc(), 500)
    
# -----------------------------
# 🔥 ITEMS
# -----------------------------
def updateGraph(group_data,payerId,giveToM,giveAmt):
    if(giveToM == payerId):
        return
    giveAmt = float(giveAmt) + group_data['groupGraph'][payerId][giveToM]
    group_data['groupGraph'][payerId][giveToM] = 0
    if(giveAmt==0): return             
    for gM in group_data['groupMembers']:
        if(giveAmt>0):
            if(gM!=giveToM):
                extrapayamt = group_data['groupGraph'][giveToM][gM]
                furamt = min(giveAmt,extrapayamt)
                if(gM == payerId):
                    group_data['groupGraph'][giveToM][gM]-=furamt
                else:
                    group_data['groupGraph'][giveToM][gM]-=furamt
                    group_data['groupGraph'][payerId][gM]+=furamt
                    
                giveAmt-=furamt
    
    for gM in group_data['groupMembers']:
        if(giveAmt!=0):
            if(gM!=payerId):

                dueamt = group_data['groupGraph'][gM][payerId]
                furamt = min(dueamt,giveAmt)
                if(giveToM ==  gM):
                    group_data['groupGraph'][gM][payerId]-=furamt
                else:
                    group_data['groupGraph'][gM][payerId]-=furamt
                    group_data['groupGraph'][gM][giveToM]+=furamt
        
                giveAmt-=furamt
    if(giveAmt>0):    
        group_data['groupGraph'][payerId][giveToM]+=giveAmt
                    

@app.route("/items", methods=["GET"])
def get_items():
    try:
        items = db.reference("items").get() or {}
        result = [{**v, "itemId": k} for k, v in items.items()]
        return safe_json_response("success", "Items fetched", wrap_data("items", result))
    except Exception:
        return safe_json_response("error", "Failed to fetch items", traceback.format_exc(), 500)

@app.route("/items", methods=["DELETE"])
def delete_item():
    try:
        # Get itemId from query params
        itemId = request.args.get("itemId")
        if not itemId:
            return safe_json_response("error", "itemId missing", code=400)

        # Fetch item
        item_ref = db.reference(f"items/{itemId}")
        item = item_ref.get()
        if not item:
            return safe_json_response("error", "Item not found", code=404)

        groupId = item.get("itemGroupId")
        if groupId:
            group_ref = db.reference(f"groups/{groupId}")
            group = group_ref.get() or {}

            # Only update groupGraph if it exists
            if "groupGraph" in group:
                payerId = item["itemPayer"][0]  # assuming first payer
                spliterList = item.get("itemSpliter", [])
                spliterValue = item.get("itemSpliterValue", [])

                for i in range(len(spliterList)):
                    receiverId = spliterList[i]
                    giveAmt = spliterValue[i]
                    updateGraph(group,receiverId,payerId,giveAmt)
                    
            # Remove item from group's item list
            if "groupItems" in group and itemId in group["groupItems"]:
                group["groupItems"].remove(itemId)

            # Save updated group
            group_ref.set(group)

        # Delete item from items collection
        item_ref.delete()

        return safe_json_response("success", "Item deleted")

    except Exception:
        import traceback
        return safe_json_response("error", "Failed to delete item", traceback.format_exc(), 500)



@app.route("/items/create",methods=["POST"])
def create_item():
    data = request.get_json()
    doc_ref = db.reference("items")
    item_dict = dict(data)
    if('itemName' in item_dict and
       'itemDateUpdate' in item_dict and
       'itemTimeUpdate' in item_dict and
       'itemTotalAmount' in item_dict and
       'itemPayer' in item_dict and
       'itemSpliter' in item_dict and
       'itemSpliterValue' in item_dict and
       'itemGroupId' in item_dict):
        new_doc_ref = doc_ref.push()
        data["itemId"] = new_doc_ref.key
        
        
        
        group_id = data["itemGroupId"]
        group_ref = db.reference("groups").child(group_id)
        group_data = group_ref.get()
        if(group_data is not None):    
            if('groupItems' not in group_data):
                group_data['groupItems'] = []
            group_data["groupItems"].append(data["itemId"])
            
            
            # balance group graph
            payerId = data["itemPayer"][0]
            spliterList = data['itemSpliter']
            splitervalue = data['itemSpliterValue']
            totalamount = data['itemTotalAmount']
            
            for i in range(0,len(spliterList)):
                giveToM = data['itemSpliter'][i]
                giveAmt = float(data['itemSpliterValue'][i])
                updateGraph(group_data,payerId,giveToM,giveAmt)
                '''
                if(giveToM == payerId):
                    continue
                
                
                giveAmt = giveAmt + group_data['groupGraph'][payerId][giveToM]
                group_data['groupGraph'][payerId][giveToM] = 0
                
                if(giveAmt==0): continue
                for gM in group_data['groupMembers']:
                    if(giveAmt>0):
                        if(gM!=giveToM):
                            extrapayamt = group_data['groupGraph'][giveToM][gM]
                            furamt = min(giveAmt,extrapayamt)
                            if(gM == payerId):
                                group_data['groupGraph'][giveToM][gM]-=furamt
                            else:
                                group_data['groupGraph'][giveToM][gM]-=furamt
                                group_data['groupGraph'][payerId][gM]+=furamt
                                
                            giveAmt-=furamt
                        
                
                for gM in group_data['groupMembers']:
                    if(giveAmt!=0):
                        if(gM!=payerId):

                            dueamt = group_data['groupGraph'][gM][payerId]
                            furamt = min(dueamt,giveAmt)
                            if(giveToM ==  gM):
                                group_data['groupGraph'][gM][payerId]-=furamt
                            else:
                                group_data['groupGraph'][gM][payerId]-=furamt
                                group_data['groupGraph'][gM][giveToM]+=furamt
                    
                            giveAmt-=furamt
                if(giveAmt>0):
                    group_data['groupGraph'][payerId][giveToM]+=giveAmt
                '''  
        
        group_ref.set(group_data)
        new_doc_ref.set(data)
        return "item created",201
    else:
        return "item key wrong",404
    
# @app.route("/items/create", methods=["POST"])
# def create_item():
#     try:
#         data = get_json_data()
#         required = [
#             "itemName", "itemDateUpdate", "itemTimeUpdate",
#             "itemTotalAmount", "itemPayer", "itemSpliter",
#             "itemSpliterValue", "itemGroupId"
#         ]
#         for key in required:
#             if key not in data:
#                 return safe_json_response("error", f"Missing field: {key}", code=400)

#         # Create item
#         item_ref = db.reference("items").push()
#         data["itemId"] = item_ref.key
#         item_ref.set(data)

#         # Add item to group
#         group_ref = db.reference(f"groups/{data['itemGroupId']}")
#         group = group_ref.get()
#         if group:
#             group.setdefault("groupItems", [])
#             safe_append(group["groupItems"], data["itemId"])
#             group_ref.update({"groupItems": group["groupItems"]})

#         return safe_json_response("success", "Item created", {"item": data}, 201)
#     except Exception:
#         return safe_json_response("error", "Failed to create item", traceback.format_exc(), 500)

@app.route("/items/<itemId>", methods=["GET"])
def get_item(itemId):
    try:
        item = db.reference(f"items/{itemId}").get()
        if not item:
            return safe_json_response("error", "Item not found", code=404)
        item["itemId"] = itemId
        return safe_json_response("success", "Item fetched", {"item": item})
    except Exception:
        return safe_json_response("error", "Failed to fetch item", traceback.format_exc(), 500)

@app.route("/items/update-item", methods=["PUT"])
def update_item():
    try:
        data = get_json_data()
        itemId = data.get("itemId")
        if not itemId:
            return safe_json_response("error", "itemId missing", code=400)

        item_ref = db.reference(f"items/{itemId}")
        item = item_ref.get()
        if not item:
            return safe_json_response("error", "Item not found", code=404)

        for k, v in data.items():
            if k != "itemId":
                item[k] = v
        item_ref.update(item)
        return safe_json_response("success", "Item updated", {"item": item})
    except Exception:
        return safe_json_response("error", "Failed to update item", traceback.format_exc(), 500)



# -----------------------------
# 🔥 GROUPS
# -----------------------------
@app.route("/groups", methods=["GET"])
def get_groups():
    try:
        groups = db.reference("groups").get() or {}
        result = []
        for k, v in groups.items():
            group = v.copy()
            group["groupId"] = k
            result.append(group)
        return safe_json_response("success", "Groups fetched", wrap_data("groups", result))
    except Exception:
        return safe_json_response("error", "Failed to fetch groups", traceback.format_exc(), 500)

@app.route("/groups/create", methods=["POST"])
def create_group():
    try:
        data = get_json_data()
        members = data.get("groupMembers")
        if not members or not isinstance(members, list):
            return safe_json_response("error", "groupMembers must be a non-empty list", 400)

        group_ref = db.reference("groups").push()
        data["groupId"] = group_ref.key
        group_ref.set(data)

        # Update user references
        for userId in members:
            user_ref = db.reference(f"users/{userId}")
            user = user_ref.get()
            if user:
                user.setdefault("groupIds", [])
                safe_append(user["groupIds"], data["groupId"])
                user_ref.update({"groupIds": user["groupIds"]})

        return safe_json_response("success", "Group created", {"group": data}, 201)
    except Exception:
        return safe_json_response("error", "Failed to create group", traceback.format_exc(), 500)

@app.route("/groups/getGroup", methods=["POST"])
def get_group_by_id():
    data = get_json_data()
    groupId = data.get("groupId") or data.get("value")
    group = db.reference(f"groups/{groupId}").get()
    print(group)
    if not group:
        return safe_json_response("error", "Group not found", code=404)
    group["groupId"] = groupId
    print(group)
    return safe_json_response("success", "Group fetched", {"group": group})


@app.route("/groups/membersDetail",methods=["POST"])
def get_group_members_detail():
    try:
        group_id = request.get_json()
        users = []
        users_data = db.reference('users').get()
        for user_id in db.reference(f"groups").get()[group_id]['groupMembers']:
            users.append(users_data[user_id])
        return jsonify(users),200
    except Exception as e:
        return f"Group member detail Error : {e}",404
    
@app.route("/groups/members/<groupId>", methods=["GET"])
def get_group_members(groupId):
    try:
        group = db.reference(f"groups/{groupId}").get()
        if not group:
            return safe_json_response("error", "Group not found", code=404)
        members = group.get("groupMembers") or []
        return safe_json_response("success", "Members fetched", wrap_data("members", members))
    except Exception:
        return safe_json_response("error", "Failed to fetch members", traceback.format_exc(), 500)


@app.route("/groups/expenseDetail", methods=["POST"])
def get_group_expense_detail():
    try:
        # Read raw body
        group_id = request.get_data(as_text=True).strip()

        print("🔥 Raw incoming:", group_id)

        # Remove extra quotes:  '"abc123"' → abc123
        group_id = group_id.strip('"')

        print("✅ Clean groupId:", group_id)

        # Fetch group info
        group_ref = db.reference("groups").child(group_id)
        group_data = group_ref.get()

        if group_data is None or "groupGraph" not in group_data:
            return jsonify({"expenseDetail": []}), 200

        graph = group_data["groupGraph"]

        # -------------------------
        #  FETCH ALL USERS NAMES
        # -------------------------
        users_ref = db.reference("users")
        users = users_ref.get() or {}  # all users

        def get_name(uid):
            return users.get(uid, {}).get("name", uid)  # fallback to UID if missing

        expense_lines = []

        # -------------------------
        # BUILD RESULT
        # -------------------------
        for payer_id, receivers in graph.items():
            payer_name = get_name(payer_id)

            for receiver_id, amount in receivers.items():
                if amount > 0:
                    receiver_name = get_name(receiver_id)

                    expense_lines.append(
                        f"{payer_name} get back from {receiver_name}: ₹{amount}"
                    )

        return jsonify({"expenseDetail": expense_lines}), 200

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500

    
    
    # -----------------------------
# 🔥 EXPENSE DETAIL FOR CURRENT USER
# -----------------------------
@app.route("/groups/expenseDetailbyCurrentUser", methods=["POST"])
def get_current_user_expense_detail():
    try:
        data = request.get_json(force=True)
        group_id = data.get("groupId")
        current_user_id = data.get("currentUserId")

        if not group_id or not current_user_id:
            return jsonify({"error": "groupId and currentUserId required"}), 400

        # Fetch group data
        group_ref = db.reference("groups").child(group_id)
        group_data = group_ref.get()

        if group_data is None or "groupGraph" not in group_data:
            return jsonify({"expenseDetail": []}), 200

        graph = group_data["groupGraph"]

        # -------------------------
        # FETCH ALL USERS
        # -------------------------
        users_data = db.reference("users").get() or []

        # Safe helper to get user name from UID
        def get_name(uid):
            if isinstance(users_data, dict):
                return users_data.get(uid, {}).get("name", uid)
            elif isinstance(users_data, list):
                # if users_data is a list, search for matching uid
                for user in users_data:
                    if isinstance(user, dict) and user.get("userId") == uid:
                        return user.get("name", uid)
                return uid
            return uid

        expense_lines = []

        # -------------------------
        # Expenses current user owes
        # -------------------------
        if current_user_id in graph:
            for receiver_id, amount in graph[current_user_id].items():
                if amount > 0:
                    payer_name = "You"
                    receiver_name = get_name(receiver_id)
                    expense_lines.append(f"{payer_name} get back from {receiver_name}: ₹{amount}")

        # -------------------------
        # Expenses others owe current user
        # -------------------------
        for payer_id, receivers in graph.items():
            if payer_id == current_user_id:
                continue
            if current_user_id in receivers and receivers[current_user_id] > 0:
                payer_name = get_name(payer_id)
                amount = receivers[current_user_id]
                expense_lines.append(f"You owes {payer_name}: ₹{amount}")

        return jsonify({"expenseDetail": expense_lines}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    
    
@app.route("/groups/items",methods=["POST"])
def get_group_items():
    start_time = time.time()
    try:
        data = request.get_json()
        group_id = request.get_json()
        group_data = db.reference(f"groups").get()[group_id]
        if('groupItems' not in group_data):
            return jsonify([]),200
        else:
            items = []
            for item_id in group_data['groupItems']:
                items.append(db.reference("items").get()[item_id])
            end_time = time.time()
            elapsed_time = end_time - start_time
            print("Time taken:", elapsed_time, "seconds")
            return jsonify(items),200
        
    except Exception as e:
        return f"Group Item List Error : {e}",404
    
# @app.route("/groups/items", methods=["POST"])
# def get_group_items():
#     try:
#         data = get_json_data()
#         groupId = data.get("groupId") or data.get("value")
#         group = db.reference(f"groups/{groupId}").get()
#         if not group:
#             return safe_json_response("error", "Group not found", code=404)

#         items = []
#         for itemId in group.get("groupItems", []):
#             item = db.reference(f"items/{itemId}").get()
#             if item:
#                 item["itemId"] = itemId
#                 items.append(item)

#         return safe_json_response("success", "Group items fetched", wrap_data("items", items))
#     except Exception:
#         return safe_json_response("error", "Failed to fetch group items", traceback.format_exc(), 500)
@app.route("/groups/addMember", methods=["PUT"])
def add_member_to_group():
    try:
        data = request.get_json()
        group_id = data['groupId']

        # Convert email to Firebase-safe key
        member_email = (
            data['memberEmail']
            .replace('.', '_dot_')
            .replace('@', '_at_')
        )

        # Fetch userId of member
        user_email_ref = db.reference('usersAsEmailKey').get()
        if member_email not in user_email_ref:
            return {"message": "User not found"}, 404

        member_id = user_email_ref[member_email]['userId']
        data['memberId'] = member_id

        # ----- Fetch group -----
        group_ref = db.reference("groups").child(group_id)
        group = group_ref.get()

        if group is None:
            return {"message": "Group not found"}, 404

        # Ensure groupMembers exists
        group.setdefault("groupMembers", [])

        # Add member if not already inside
        if member_id not in group["groupMembers"]:
            group["groupMembers"].append(member_id)

        # Ensure groupGraph exists
        group.setdefault("groupGraph", {})
        group["groupGraph"].setdefault(member_id, {})

        # Build graph
        for gm in group["groupMembers"]:
            if gm == member_id:
                continue
            group["groupGraph"].setdefault(gm, {})
            group["groupGraph"][gm][member_id] = 0
            group["groupGraph"][member_id][gm] = 0

        # Save updated group
        group_ref.set(group)

        # ----- Update user -----
        user_ref = db.reference("users").child(member_id)
        user_data = user_ref.get()

        if user_data is not None:
            user_data.setdefault("groupIds", [])
            if group_id not in user_data["groupIds"]:
                user_data["groupIds"].append(group_id)
                user_ref.set(user_data)

        return {"message": "Member added"}, 200

    except Exception as e:
        return {"error": f"Member add error: {e}"}, 500

# @app.route("/groups/addMember", methods=["PUT"])
# def add_member():
#     try:
#         data = get_json_data()
#         groupId = data.get("groupId")
#         email = data.get("memberEmail", "").replace(".", "_dot_").replace("@", "_at_")
#         email_ref = db.reference(f"usersAsEmailKey/{email}").get()
#         if not email_ref:
#             return safe_json_response("error", "User email not found", code=404)

#         memberId = email_ref["userId"]
#         group_ref = db.reference(f"groups/{groupId}")
#         group = group_ref.get()
#         if not group:
#             return safe_json_response("error", "Group not found", code=404)

#         group.setdefault("groupMembers", [])
#         safe_append(group["groupMembers"], memberId)
#         group_ref.update({"groupMembers": group["groupMembers"]})

#         # Update user
#         user_ref = db.reference(f"users/{memberId}")
#         user = user_ref.get()
#         if user:
#             user.setdefault("groupIds", [])
#             safe_append(user["groupIds"], groupId)
#             user_ref.update({"groupIds": user["groupIds"]})

#         return safe_json_response("success", "Member added", {"memberId": memberId})
#     except Exception:
#         return safe_json_response("error", "Failed to add member", traceback.format_exc(), 500)

@app.route("/groups", methods=["DELETE"])
def delete_group():
    try:
        data = get_json_data()
        groupId = data.get("groupId")
        if not groupId:
            return safe_json_response("error", "groupId missing", 400)

        group_ref = db.reference(f"groups/{groupId}")
        group = group_ref.get()
        if not group:
            return safe_json_response("error", "Group not found", 404)

        # Remove references from users
        for userId in group.get("groupMembers", []):
            user_ref = db.reference(f"users/{userId}")
            user = user_ref.get()
            if user and "groupIds" in user and groupId in user["groupIds"]:
                user["groupIds"].remove(groupId)
                user_ref.update({"groupIds": user["groupIds"]})

        group_ref.delete()
        return safe_json_response("success", "Group deleted")
    except Exception:
        return safe_json_response("error", "Failed to delete group", traceback.format_exc(), 500)

# -----------------------------
# 🔥 SERVER RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    app.run(host="0.0.0.0", port=port, debug=True)
