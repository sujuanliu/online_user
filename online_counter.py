import pymysql
import time, datetime
import json
import threading
import redis
import paramiko, socket

pymysql.install_as_MySQLdb()

def run(region, ip):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, ssh_port, "root", sshpass, timeout=TIMEOUT, look_for_keys=False)
        stdin, stdout, stderr = ssh.exec_command(
            "strongswan leases|grep online |grep -v Leases|awk '{print $3}'|sort -u |wc -l"
        )
        rst = str(stdout.read().decode("utf-8")).replace("\n", "")
        result[region] = {ip: int(rst)}
        ssh.close()
    except (
        paramiko.ssh_exception.SSHException,
        socket.error,
        socket.timeout,
        EOFError,
    ):
        print("Failed: %s %s" % (region, ip))
        result[region] = {ip: set_previous_value(region, ip)}


def get_iplist(mysql_ip, mysql_port, mysql_user, mysql_password, mysql_db):
    conn = pymysql.connect(
        user=mysql_user,
        passwd=mysql_password,
        host=mysql_ip,
        port=mysql_port,
        db=mysql_db,
        charset="utf8",
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT servername, if(has_agent=1,proxyip,serverip) as ip FROM jiguang.vpn_server where status=1;"
    )
    query_result = cursor.fetchall()
    cursor.close()
    conn.close()
    return query_result


def write_redis(d):
    r = redis.StrictRedis(redis_host, port=redis_port, password=redis_pwd, db=0)
    if d:
        r.set(redis_key, d)


def get_redis(key):
    r = redis.StrictRedis(redis_host, port=redis_port, password=redis_pwd, db=0)
    redis_result = r.get(key)
    return eval(redis_result) if redis_result else None


def set_previous_value(region, ip):
    try:
        json_value = get_redis(redis_key)
        if json_value:
            online_num = (
                value.get(ip) for key, value in json_value.items() if key == region
            )
            return int(online_num.__next__())
        else:
            return -1
    except StopIteration as err:
        return -1


if __name__ == "__main__":
    while True:
        result = {}
        print("%s Start..." % (datetime.datetime.now().strftime("%b-%d-%Y %H:%M:%S")))
        start_time = time.time()
        mysql_result = get_iplist(
            mysql_ip, mysql_port, mysql_user, mysql_password, mysql_db
        )

        threads = []
        for server in mysql_result:
            thread = threading.Thread(target=run, args=(server[0], server[1]))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        json_result = json.dumps(result, ensure_ascii=False)
        write_redis(json_result)
        end_time = time.time()
        time_used = end_time - start_time
        print("Total_time:%s 秒" % time_used)
        print(json_result)
        print("%s End!\n" % (datetime.datetime.now().strftime("%b-%d-%Y %H:%M:%S")))
        if time_used < 10.0:
            time.sleep(10.0 - time_used)
        else:
            time.sleep(3)
