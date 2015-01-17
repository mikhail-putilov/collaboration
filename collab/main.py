# coding=utf-8


# __author__ = 'snowy'

# from twisted.internet import stdio
# from twisted.protocols import basic


# class SublimeTextEmulator(basic.LineReceiver):
#     def connectionMade(self):
#         self.transport.write('>>> ')

#     def lineReceived(self, line):
#         self.sendLine('Echo: ' + line)
#         self.transport.write('>>> ')


# def main():
#     stdio.StandardIO(SublimeTextEmulator())
#     from twisted.internet import reactor

#     reactor.run()


# if __name__ == '__main__':
#     main()
