<template>
  <div class="flex items-center justify-center min-h-[70vh]">
    <div class="w-full max-w-md">
      <h1 class="text-2xl font-bold text-white text-center mb-6">Create your account</h1>
      <div class="flex justify-center">
        <SignUp
          :routing="'path'"
          :path="'/register'"
          :sign-in-url="'/login'"
          appearance="{}"
        />
      </div>
    </div>
  </div>
</template>
