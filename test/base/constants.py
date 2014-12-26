# coding=utf-8
__author__ = 'snowy'
initialText = u"""Hamlet: Do you see yonder cloud that's almost in shape of a camel?
Polonius: By the mass, and 'tis like a camel, indeed.
Hamlet: Methinks it is like a weasel.
Polonius: It is backed like a weasel.
Hamlet: Or like a whale?
Polonius: Very like a whale.
-- Shakespeare"""
textVer1 = u"""Гамл: Do you see yonder cloud that's almost in shape of a camel?
Polonius: By the mass, and 'tis like a camel, indeed.
Hamlet: Methinks it is like a weasel.
Polonius: It is backed like a weasel.
Hamlet: Or like a whale?
Polonius: Very like a whale.
-- Shakespeare"""
textVer2 = u"""Гамлет: что ты видишь yonder cloud that's almost in shape of a camel?
Polonius: By the mass, and 'tis like a camel, indeed.
Hamlet: Methinks it is like a weasel.
Polonius: It is backed like a weasel.
Hamlet: Or like a whale?
Polonius: Very like a whale.
-- Shakespeare"""
textVer3 = u"""Гамлет: что ты видишь облачко, которое почin shape of a camel?
Polonius: By the mass, and 'tis like a camel, indeed.
Hamlet: Methinks it is like a weasel.
Polonius: It is backed like a weasel.
Hamlet: Or like a whale?
Polonius: Very like a whale.
-- Shakespeare"""
textVer4 = u"""Гамлет: что ты видишь облачко, которое почти как верблюд?
Polonius: By the mass, and 'tis like a camel, indeed.
Hamlet: Methinks it is like a weasel.
Polonius: It is backed like a weasel.
Hamlet: Or like a whale?
Polonius: Very like a whale.
-- Shakespeare"""
textVersionSeq = [initialText, textVer1, textVer2, textVer3, textVer4]
patchedText = u"""Hamlet: Do you see the cloud over there that's almost the shape of a camel?
Polonius: By golly, it is like a camel, indeed.
Hamlet: I think it looks like a weasel.
Polonius: It is shaped like a weasel.
Hamlet: Or like a whale?
Polonius: It's totally like a whale.
-- Shakespeare"""
patch = u"""@@ -16,21 +16,29 @@
 see
-yonder
+the
  cloud
+over there
 that
@@ -47,18 +47,19 @@
  almost
-in
+the
  shape o
@@ -86,24 +86,18 @@
  By
-the mass, and 't
+golly, it
 is l
@@ -129,21 +129,23 @@
 et:
-Me
+I
 think
-s
  it
-i
+look
 s li
@@ -177,12 +177,12 @@
  is
-back
+shap
 ed l
@@ -234,11 +234,19 @@
 us:
-Ver
+It's totall
 y li"""