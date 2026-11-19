# LiteRT-LM: native code calls into its classes, and it reads the companion's tools (a ToolSet) by reflection.
-keep class com.google.ai.edge.litertlm.** { *; }
-keep class * implements com.google.ai.edge.litertlm.ToolSet { *; }
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod,RuntimeVisibleParameterAnnotations
-keep class kotlin.Metadata { *; }
