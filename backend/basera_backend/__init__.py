# Enable PyMySQL as MySQLdb drop-in for shared hosting (Namecheap / cPanel).
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    pass
